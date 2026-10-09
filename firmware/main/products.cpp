#include "products.hpp"
#include "product_catalog.hpp"
#include "settings_file.hpp"
#include "offline.hpp"
#include "offline_catalog.hpp"
#include "module_policy.hpp"
#include "erp_fonts.h"
#include "cJSON.h"
#include "mbedtls/sha256.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <ctime>
#include <sys/stat.h>
#include <cctype>
#include <initializer_list>
#include <cstdint>
#include <atomic>

namespace tab5 { namespace {
using namespace catalog;
constexpr unsigned page_size=8;
struct Row {int id;bool active,low;char sku[33],name[481],category[321],sale[24],stock[24];};
enum class Mode { List, Detail, Form, Confirm };
enum class Action { Browse, Refresh, Select, New, Edit, Save, Confirm, Deactivate };
struct Command {Action action;unsigned page;int id;char query[481],category[321];bool inactive;Product product;};
struct View {unsigned serial=0,page=0,total=0;Mode mode=Mode::List;bool busy=false;char message[256]{};Row rows[page_size]{};unsigned count=0;Product selected;};
View view;SemaphoreHandle_t mutex;QueueHandle_t queue;
lv_obj_t *root,*heading,*message,*query,*category,*inactive,*form,*inputs[field_count],*active,*keyboard,*rows[page_size],*buttons[6];
lv_group_t* group;void (*return_home)();bool visible=false,light=false,can_create=false,can_edit=false,can_delete=false;
std::atomic<bool> cancel_requested{false};
unsigned drawn=0;char gui_permissions[512]{};
const char* labels[]={"SKU *","GTIN/EAN (opcional)","Nome *","Descrição","Categoria","Unidade *","Custo (R$)","Venda (R$) *","Estoque atual","Estoque mínimo","Estoque máximo (opcional)","NCM (opcional)","CEST (opcional)","Origem 0 a 8 (opcional)"};
void publish(const char* text,bool busy=false){xSemaphoreTake(mutex,portMAX_DELAY);snprintf(view.message,sizeof(view.message),"%s",text);view.busy=busy;++view.serial;xSemaphoreGive(mutex);}
std::string cache_path(const char*){return std::string("/sdcard/ERP/cache/catalog-")+offline_scope()+".enc";}
std::string usable_cache(const std::string& path){if(catalog_path_valid(path))return path;if(catalog_path_valid(path+".bak"))return path+".bak";return {};}
const char* error_text(int code,const char* response){
    static char text[256];auto* data=cJSON_Parse(response);const char* detail=json_text(cJSON_GetObjectItemCaseSensitive(data,"error"),"message");
    snprintf(text,sizeof(text),"%s",detail[0]?detail:code<=0?"Sem confirmação da API. Atualize antes de repetir a operação.":"API recusou a operação. Confira os dados e permissões.");cJSON_Delete(data);return text;
}
void cleanup_legacy_cache(const char* api){if(!api)return;uint8_t hash[32];mbedtls_sha256(reinterpret_cast<const uint8_t*>(api),strlen(api),hash,0);char hex[65];for(unsigned i=0;i<32;++i)snprintf(hex+i*2,3,"%02x",hash[i]);erase_settings_files(std::string("/sdcard/ERP/cache/products-")+hex+".jsonl");}
bool sync_cache(const std::string& path,ProductTransport transport){
    mkdir("/sdcard/ERP/cache",0755);auto base=usable_cache(path);CatalogHeader prior{};if(!base.empty()){CatalogFile old;if(old.read(base))prior=old.header;}
    const auto delta_path=path+".delta",temp=path+".tmp";remove_settings_path(delta_path);
    CatalogFile delta;static char response[16385];unsigned after=0,revision=0,count=0;bool ok=true;CatalogHeader target{};
    do{
        if(cancel_requested.load()){publish("Atualização interrompida. Cache anterior preservado.");ok=false;break;}
        std::string url="/api/v1/sync/products?limit=2&since="+std::to_string(prior.revision)+"&after_id="+std::to_string(after);
        if(revision)url+="&revision="+std::to_string(revision)+"&epoch="+std::string(target.epoch);else if(prior.revision)url+="&epoch="+std::string(prior.epoch);
        int code=transport("GET",url.c_str(),nullptr,response,sizeof(response));
        if(code==409&&!after&&prior.revision){prior=CatalogHeader{};base.clear();continue;}
        if(code!=200){publish(error_text(code,response));ok=false;break;}
        auto* data=cJSON_Parse(response);auto* items=cJSON_GetObjectItemCaseSensitive(data,"items");unsigned received=number(data,"revision");
        if(!data||number(data,"format")!=2||!cJSON_IsArray(items)||!received||(revision&&received!=revision)||strlen(json_text(data,"epoch"))!=36){cJSON_Delete(data);publish("Resposta incremental inválida. Cache preservado.");ok=false;break;}
        if(!revision){revision=received;target.revision=received;target.time=time(nullptr);snprintf(target.epoch,sizeof(target.epoch),"%s",json_text(data,"epoch"));if(!delta.write(delta_path,target)){cJSON_Delete(data);publish("microSD sem escrita. Cache preservado.");ok=false;break;}}
        unsigned last=after;cJSON* item;cJSON_ArrayForEach(item,items){unsigned id=number(item,"id");if(id<=last){ok=false;break;}last=id;char* line=cJSON_PrintUnformatted(item);if(!line||!delta.append(line)||++count>10000)ok=false;cJSON_free(line);if(!ok)break;}
        auto* next=cJSON_GetObjectItemCaseSensitive(data,"next_id");unsigned next_id=cJSON_IsNumber(next)?next->valueint:0;auto* complete=cJSON_GetObjectItemCaseSensitive(data,"complete");if(!next||!cJSON_IsBool(complete)||cJSON_IsTrue(complete)==static_cast<bool>(next_id)||number(data,"since")!=static_cast<int>(prior.revision))ok=false;if(next_id&&(next_id!=last||next_id<=after))ok=false;after=next_id;cJSON_Delete(data);
        if(!ok){publish("Catálogo inválido ou excede limite. Cache preservado.");break;}
        char progress[140];snprintf(progress,sizeof(progress),"Sincronizando: %u produtos alterados | Base %u...",count,prior.revision);publish(progress,true);
    }while((after||(!revision&&ok))&&ok);
    if(ok){ok=delta.finish();}
    if(ok){ok=catalog_path_valid(delta_path);}
    if(ok){CatalogFile old,changes,merged;static char old_row[6002],new_row[6002];int old_rc=0,new_rc=-1;
        if(!base.empty()){if(!old.read(base))ok=false;else old_rc=old.next(old_row,sizeof(old_row));}
        if(!changes.read(delta_path)||!merged.write(temp,target))ok=false;else new_rc=changes.next(new_row,sizeof(new_row));
        auto id=[](const char* row){auto* j=cJSON_Parse(row);int result=number(j,"id");cJSON_Delete(j);return result;};unsigned merged_count=0;
        while(ok&&(old_rc>0||new_rc>0)){if(cancel_requested.load()){ok=false;break;}int old_id=old_rc>0?id(old_row):2147483647,new_id=new_rc>0?id(new_row):2147483647;
            if(new_rc>0&&(old_rc<=0||new_id<=old_id)){ok=merged.append(new_row);if(old_rc>0&&old_id==new_id)old_rc=old.next(old_row,sizeof(old_row));new_rc=changes.next(new_row,sizeof(new_row));}
            else{ok=merged.append(old_row);old_rc=old.next(old_row,sizeof(old_row));}if(old_rc<0||new_rc<0)ok=false;if((++merged_count&31)==0)vTaskDelay(1);
        }
        if(ok)ok=merged.finish();
    }
    if(ok){ok=catalog_path_valid(temp);if(ok&&base==path+".bak"&&access(path.c_str(),F_OK)==0){auto damaged=path+".damaged-"+std::to_string(time(nullptr));if(access(damaged.c_str(),F_OK)==0||rename(path.c_str(),damaged.c_str())!=0)ok=false;}if(ok)ok=commit_settings_temp(path);}
    remove_settings_path(delta_path);
    if(!ok){remove_settings_path(temp);publish("Sincronização não concluída. Cache anterior preservado; tente novamente.");}
    return ok;
}
bool browse(const std::string& path,const Command& cmd,bool online){
    auto usable=usable_cache(path);if(usable.empty()){publish("Cache ausente ou corrompido. Conecte à API e atualize.");return false;}
    CatalogFile file;if(!file.read(usable))return false;static char line[6002];static View next;next=View{};next.page=cmd.page;next.mode=Mode::List;auto search=folded(cmd.query),category_filter=folded(cmd.category);int rc;
    while((rc=file.next(line,sizeof(line)))>0){auto* data=cJSON_Parse(line);static Product p;bool decoded=decode(data,p);bool match=decoded&&(cmd.inactive||p.active)&&(category_filter.empty()||folded(p.category)==category_filter)&&(search.empty()||folded(p.sku).find(search)!=std::string::npos||folded(p.name).find(search)!=std::string::npos||search==p.barcode);
        if(match){unsigned index=next.total++;if(index>=cmd.page*page_size&&next.count<page_size){auto& row=next.rows[next.count++];row.id=p.id;row.active=p.active;row.low=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(data,"stock_low"));snprintf(row.sku,sizeof(row.sku),"%s",p.sku);snprintf(row.name,sizeof(row.name),"%s",p.name);snprintf(row.category,sizeof(row.category),"%s",p.category);snprintf(row.sale,sizeof(row.sale),"%s",p.sale);snprintf(row.stock,sizeof(row.stock),"%s",p.stock);}}cJSON_Delete(data);}
    if(rc<0){publish("Cache corrompido. Atualize antes de consultar.");return false;}
    char date[40]="sem data";tm when{};time_t saved=file.header.time;if(saved&&gmtime_r(&saved,&when))strftime(date,sizeof(date),"%d/%m/%Y %H:%M UTC",&when);
    snprintf(next.message,sizeof(next.message),"%s | Cache de %s | Revisão %u | Página %u | %u resultados%s",online?"Consulta local":"OFFLINE: consulta local",date,file.header.revision,cmd.page+1,next.total,usable==path?"":" | Backup recuperado");xSemaphoreTake(mutex,portMAX_DELAY);next.serial=view.serial+1;view=next;xSemaphoreGive(mutex);return true;
}
bool select_cached(const std::string&,int id,Product& product){static char line[6002];if(!offline_product_get(id,line,sizeof(line)))return false;auto* data=cJSON_Parse(line);bool ok=decode(data,product);cJSON_Delete(data);return ok;}
void queue_command(Action action,unsigned page=0,int id=0){
    static Command cmd;cmd=Command{};cmd.action=action;cmd.page=page;cmd.id=id;
    snprintf(cmd.query,sizeof(cmd.query),"%s",lv_textarea_get_text(query));snprintf(cmd.category,sizeof(cmd.category),"%s",lv_textarea_get_text(category));cmd.inactive=lv_obj_has_state(inactive,LV_STATE_CHECKED);
    if(action==Action::Save){xSemaphoreTake(mutex,portMAX_DELAY);cmd.product=view.selected;xSemaphoreGive(mutex);
        for(unsigned i=0;i<field_count;++i){const char* value=lv_textarea_get_text(inputs[i]);if(strlen(value)>=capacity(i)){lv_label_set_text(message,"Campo muito longo. Reduza o texto.");return;}snprintf(field(cmd.product,i),capacity(i),"%s",value);}
        cmd.product.active=lv_obj_has_state(active,LV_STATE_CHECKED);
    }
    if(xQueueSend(queue,&cmd,0)!=pdTRUE)lv_label_set_text(message,"Operação em andamento. Aguarde.");
}
void focused(lv_event_t* event){lv_keyboard_set_textarea(keyboard,lv_event_get_target_obj(event));lv_obj_scroll_to_view(lv_event_get_target_obj(event),LV_ANIM_OFF);}
void touched(lv_event_t* event){lv_obj_remove_flag(keyboard,LV_OBJ_FLAG_HIDDEN);focused(event);}
void row_event(lv_event_t* event){queue_command(Action::Select,0,static_cast<int>(reinterpret_cast<intptr_t>(lv_event_get_user_data(event))));}
void key_event(lv_event_t* event){auto key=lv_event_get_key(event);if(key==LV_KEY_ESC){visible=false;cancel_requested.store(true);lv_obj_add_flag(root,LV_OBJ_FLAG_HIDDEN);return_home();}}
void button_event(lv_event_t* event){
    unsigned index=static_cast<unsigned>(reinterpret_cast<uintptr_t>(lv_event_get_user_data(event)));static View snapshot;xSemaphoreTake(mutex,portMAX_DELAY);snapshot=view;xSemaphoreGive(mutex);
    if(index==5){visible=false;cancel_requested.store(true);lv_obj_add_flag(root,LV_OBJ_FLAG_HIDDEN);return_home();return;}
    if(snapshot.mode==Mode::List){if(index==0)queue_command(Action::Browse,snapshot.page?snapshot.page-1:0);else if(index==1)queue_command(Action::Browse,snapshot.page+1);else if(index==2)queue_command(Action::New);else if(index==3)queue_command(Action::Refresh);else queue_command(Action::Browse);}
    else if(snapshot.mode==Mode::Form){if(index==0)queue_command(Action::Save);else queue_command(Action::Browse);}
    else if(index==0)queue_command(Action::Edit);else if(index==1)queue_command(snapshot.mode==Mode::Confirm?Action::Deactivate:Action::Confirm);else queue_command(Action::Browse);
}
void filter_event(lv_event_t*){queue_command(Action::Browse);}
void theme_tree(lv_obj_t* obj){
    lv_obj_set_style_text_color(obj,lv_color_hex(light?0x0f172a:0xf8fafc),0);
    if(lv_obj_check_type(obj,&lv_button_class)||lv_obj_check_type(obj,&lv_textarea_class))lv_obj_set_style_bg_color(obj,lv_color_hex(light?0xe2e8f0:0x334155),0);
    for(unsigned i=0;i<lv_obj_get_child_count(obj);++i)theme_tree(lv_obj_get_child(obj,i));
}
} // namespace
void products_create(lv_display_t* display,void (*home)()){
    return_home=home;mutex=xSemaphoreCreateMutex();queue=xQueueCreate(1,sizeof(Command));group=lv_group_create();
    root=lv_obj_create(lv_display_get_screen_active(display));lv_obj_set_size(root,1280,720);lv_obj_set_pos(root,0,0);lv_obj_remove_flag(root,LV_OBJ_FLAG_SCROLLABLE);lv_obj_set_style_pad_all(root,12,0);
    heading=lv_label_create(root);lv_obj_set_pos(heading,8,4);lv_obj_set_style_text_font(heading,&erp_font_pt_28,0);lv_label_set_text(heading,"Produtos");
    message=lv_label_create(root);lv_obj_set_pos(message,8,45);lv_obj_set_width(message,1200);
    query=lv_textarea_create(root);lv_obj_set_pos(query,8,100);lv_obj_set_size(query,380,52);lv_textarea_set_one_line(query,true);lv_textarea_set_max_length(query,120);lv_textarea_set_placeholder_text(query,"Nome, SKU ou GTIN");
    category=lv_textarea_create(root);lv_obj_set_pos(category,408,100);lv_obj_set_size(category,340,52);lv_textarea_set_one_line(category,true);lv_textarea_set_max_length(category,80);lv_textarea_set_placeholder_text(category,"Categoria (nome exato)");
    inactive=lv_checkbox_create(root);lv_obj_set_pos(inactive,778,108);lv_checkbox_set_text(inactive,"Mostrar inativos");
    auto* filter=lv_button_create(root);lv_obj_set_pos(filter,1050,100);lv_obj_set_size(filter,160,52);lv_label_set_text(lv_label_create(filter),"Filtrar");lv_obj_center(lv_obj_get_child(filter,0));lv_obj_add_event_cb(filter,filter_event,LV_EVENT_CLICKED,nullptr);
    for(unsigned i=0;i<page_size;++i){rows[i]=lv_button_create(root);lv_obj_set_pos(rows[i],8,174+i*42);lv_obj_set_size(rows[i],1204,38);for(unsigned col=0;col<4;++col){constexpr int xpos[]={4,174,638,856},widths[]={158,452,206,314};auto* label=lv_label_create(rows[i]);lv_obj_set_pos(label,xpos[col],0);lv_obj_set_width(label,widths[col]);lv_label_set_long_mode(label,LV_LABEL_LONG_DOT);}lv_obj_add_flag(rows[i],LV_OBJ_FLAG_HIDDEN);lv_obj_add_event_cb(rows[i],key_event,LV_EVENT_KEY,nullptr);}
    form=lv_obj_create(root);lv_obj_set_pos(form,8,104);lv_obj_set_size(form,1204,240);lv_obj_set_style_pad_all(form,8,0);
    for(unsigned i=0;i<field_count;++i){unsigned col=i%3,row=i/3;auto* label=lv_label_create(form);lv_obj_set_pos(label,col*390,row*80);lv_label_set_text(label,labels[i]);inputs[i]=lv_textarea_create(form);lv_obj_set_pos(inputs[i],col*390,row*80+26);lv_obj_set_size(inputs[i],374,48);lv_textarea_set_one_line(inputs[i],true);constexpr unsigned lengths[]={32,14,120,500,80,8,13,13,16,16,16,8,7,1};lv_textarea_set_max_length(inputs[i],lengths[i]);lv_obj_add_event_cb(inputs[i],focused,LV_EVENT_FOCUSED,nullptr);lv_obj_add_event_cb(inputs[i],touched,LV_EVENT_CLICKED,nullptr);lv_obj_add_event_cb(inputs[i],key_event,LV_EVENT_KEY,nullptr);}
    active=lv_checkbox_create(form);lv_obj_set_pos(active,2*390,4*80+30);lv_checkbox_set_text(active,"Ativo");lv_obj_add_flag(form,LV_OBJ_FLAG_HIDDEN);
    for(unsigned i=0;i<6;++i){buttons[i]=lv_button_create(root);lv_obj_set_pos(buttons[i],8+i*202,550);lv_obj_set_size(buttons[i],190,48);auto* label=lv_label_create(buttons[i]);lv_obj_center(label);lv_obj_add_event_cb(buttons[i],button_event,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(i)));lv_obj_add_event_cb(buttons[i],key_event,LV_EVENT_KEY,nullptr);}
    keyboard=lv_keyboard_create(root);lv_obj_set_pos(keyboard,8,416);lv_obj_set_size(keyboard,1204,250);lv_obj_add_flag(keyboard,LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_event_cb(keyboard,[](lv_event_t*){lv_obj_add_flag(keyboard,LV_OBJ_FLAG_HIDDEN);},LV_EVENT_READY,nullptr);
    lv_obj_add_event_cb(keyboard,[](lv_event_t*){lv_obj_add_flag(keyboard,LV_OBJ_FLAG_HIDDEN);},LV_EVENT_CANCEL,nullptr);
    lv_obj_add_event_cb(query,focused,LV_EVENT_FOCUSED,nullptr);lv_obj_add_event_cb(category,focused,LV_EVENT_FOCUSED,nullptr);lv_obj_add_event_cb(query,touched,LV_EVENT_CLICKED,nullptr);lv_obj_add_event_cb(category,touched,LV_EVENT_CLICKED,nullptr);
    lv_obj_add_flag(root,LV_OBJ_FLAG_HIDDEN);lv_timer_create([](lv_timer_t*){products_render();},100,nullptr);
    // Keep filter reachable after list/form group rebuilding.
    lv_obj_set_user_data(query,filter);
}
void products_open(const char* permissions,bool light_value){
    snprintf(gui_permissions,sizeof(gui_permissions),"%s",permissions);can_create=has_module_permission(permissions,"products.create");can_edit=has_module_permission(permissions,"products.update");can_delete=has_module_permission(permissions,"products.delete");
    xQueueReset(queue);xSemaphoreTake(mutex,portMAX_DELAY);view.mode=Mode::List;view.count=0;view.total=0;view.page=0;xSemaphoreGive(mutex);
    cancel_requested.store(false);light=light_value;visible=true;drawn=0;lv_obj_set_style_bg_color(root,lv_color_hex(light?0xf1f5f9:0x111827),0);theme_tree(root);lv_obj_remove_flag(root,LV_OBJ_FLAG_HIDDEN);
    lv_obj_set_style_bg_color(form,lv_color_hex(light?0xffffff:0x1e293b),0);lv_obj_set_style_text_color(keyboard,lv_color_hex(light?0x0f172a:0xf8fafc),LV_PART_ITEMS);lv_obj_set_style_bg_color(keyboard,lv_color_hex(light?0xe2e8f0:0x334155),LV_PART_ITEMS);
    publish("Carregando produtos...",true);queue_command(Action::Browse);products_render();
}
void products_hide(){visible=false;cancel_requested.store(true);if(queue)xQueueReset(queue);if(root)lv_obj_add_flag(root,LV_OBJ_FLAG_HIDDEN);}
void products_render(){
    if(!visible){return;}
    static View next;xSemaphoreTake(mutex,portMAX_DELAY);next=view;xSemaphoreGive(mutex);if(next.serial==drawn)return;
    bool rebuild=drawn==0 || !next.busy;drawn=next.serial;lv_label_set_text(message,next.message);
    for(unsigned i=0;i<6;++i){if(next.busy&&i!=5)lv_obj_add_state(buttons[i],LV_STATE_DISABLED);else lv_obj_remove_state(buttons[i],LV_STATE_DISABLED);}
    if(!rebuild)return;
    lv_group_remove_all_objs(group);lv_group_set_default(group);for(auto* input=lv_indev_get_next(nullptr);input;input=lv_indev_get_next(input))if(lv_indev_get_type(input)==LV_INDEV_TYPE_KEYPAD)lv_indev_set_group(input,group);
    auto* filter=static_cast<lv_obj_t*>(lv_obj_get_user_data(query));bool listing=next.mode==Mode::List,editing=next.mode==Mode::Form;
    for(auto* obj:{query,category,inactive,filter}){if(listing)lv_obj_remove_flag(obj,LV_OBJ_FLAG_HIDDEN);else lv_obj_add_flag(obj,LV_OBJ_FLAG_HIDDEN);}
    if(listing){lv_label_set_text(heading,"Produtos | Consulta paginada");lv_obj_add_flag(form,LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(keyboard,LV_OBJ_FLAG_HIDDEN);lv_group_add_obj(group,query);lv_group_add_obj(group,category);lv_group_add_obj(group,inactive);lv_group_add_obj(group,filter);}
    else{char title[160];snprintf(title,sizeof(title),"Produtos | %s | ID %d | Versão %d",editing?"Cadastro / edição":next.mode==Mode::Confirm?"Confirmar inativação":"Consulta",next.selected.id,next.selected.version);lv_label_set_text(heading,title);lv_obj_remove_flag(form,LV_OBJ_FLAG_HIDDEN);lv_obj_set_height(form,editing?240:422);
        for(unsigned i=0;i<field_count;++i){if(i>=6&&i<=10){char number[24];snprintf(number,sizeof(number),"%s",field(next.selected,i));for(char* c=number;*c;++c)if(*c=='.')*c=',';lv_textarea_set_text(inputs[i],number);}else lv_textarea_set_text(inputs[i],field(next.selected,i));if(editing){lv_obj_remove_state(inputs[i],LV_STATE_DISABLED);lv_group_add_obj(group,inputs[i]);}else lv_obj_add_state(inputs[i],LV_STATE_DISABLED);}
        if(next.selected.active)lv_obj_add_state(active,LV_STATE_CHECKED);else lv_obj_remove_state(active,LV_STATE_CHECKED);
        if(editing){lv_obj_remove_state(active,LV_STATE_DISABLED);lv_group_add_obj(group,active);lv_obj_remove_flag(keyboard,LV_OBJ_FLAG_HIDDEN);lv_keyboard_set_textarea(keyboard,inputs[0]);}else{lv_obj_add_state(active,LV_STATE_DISABLED);lv_obj_add_flag(keyboard,LV_OBJ_FLAG_HIDDEN);}}
    for(unsigned i=0;i<page_size;++i){lv_obj_add_flag(rows[i],LV_OBJ_FLAG_HIDDEN);lv_obj_remove_event_cb(rows[i],row_event);if(listing&&i<next.count){auto& row=next.rows[i];char text[1100];char price[24],stock[24];snprintf(price,sizeof(price),"%s",row.sale);snprintf(stock,sizeof(stock),"%s",row.stock);for(char* c=price;*c;++c)if(*c=='.')*c=',';for(char* c=stock;*c;++c)if(*c=='.')*c=',';
            lv_label_set_text(lv_obj_get_child(rows[i],0),row.sku);lv_label_set_text(lv_obj_get_child(rows[i],1),row.name);snprintf(text,sizeof(text),"R$ %s",price);lv_label_set_text(lv_obj_get_child(rows[i],2),text);snprintf(text,sizeof(text),"%s%s%s",stock,row.low?" | Baixo":"",row.active?"":" | Inativo");lv_label_set_text(lv_obj_get_child(rows[i],3),text);lv_obj_remove_flag(rows[i],LV_OBJ_FLAG_HIDDEN);lv_obj_add_event_cb(rows[i],row_event,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<intptr_t>(row.id)));lv_group_add_obj(group,rows[i]);}}
    const char* list_titles[]={"Anterior","Próxima","Novo produto","Atualizar cache","Filtrar","Menu"};const char* form_titles[]={"Salvar","Cancelar","","","","Menu"};const char* detail_titles[]={"Editar",next.mode==Mode::Confirm?"Confirmar":"Inativar","Voltar","","","Menu"};
    for(unsigned i=0;i<6;++i){const char* caption=listing?list_titles[i]:editing?form_titles[i]:detail_titles[i];auto* label=lv_obj_get_child(buttons[i],0);lv_label_set_text(label,caption);lv_obj_center(label);lv_obj_set_y(buttons[i],editing?358:550);
        if(!caption[0]||(listing&&i==2&&!can_create)||(!listing&&!editing&&i==0&&!can_edit)||(!listing&&!editing&&i==1&&(!can_delete||!next.selected.active)))lv_obj_add_flag(buttons[i],LV_OBJ_FLAG_HIDDEN);
        else{lv_obj_remove_flag(buttons[i],LV_OBJ_FLAG_HIDDEN);lv_group_add_obj(group,buttons[i]);}
        if(listing&&((i==0&&next.page==0)||(i==1&&(next.page+1)*page_size>=next.total)))lv_obj_add_state(buttons[i],LV_STATE_DISABLED);
    }
}
bool products_handle_next(const char* permissions,const char* api,bool online,ProductTransport transport){
    static Command cmd;if(xQueueReceive(queue,&cmd,0)!=pdTRUE)return false;
    if(!has_module_permission(permissions,"products.read")){publish("Sem permissão para consultar produtos.");return true;}
    publish("Aguarde...",true);auto path=cache_path(api);
    if(cmd.action==Action::Browse || cmd.action==Action::Refresh){
        bool has_cache=!usable_cache(path).empty();bool needs_sync=cmd.action==Action::Refresh||!has_cache;
        if(needs_sync){if(!online){publish("Sem rede. Não foi possível atualizar o cache.");if(has_cache)browse(path,cmd,false);return true;}if(!sync_cache(path,transport))return true;cleanup_legacy_cache(api);}
        browse(path,cmd,online);return true;
    }
    if(cmd.action==Action::Select){static Product p;if(!select_cached(path,cmd.id,p)){publish("Produto não encontrado no cache. Atualize.");return true;}xSemaphoreTake(mutex,portMAX_DELAY);view.selected=p;view.mode=Mode::Detail;xSemaphoreGive(mutex);char detail[256];snprintf(detail,sizeof(detail),"Consulta do cache | Criado %s | Alterado %s",p.created,p.updated);publish(detail);return true;}
    if(cmd.action==Action::Edit){
        if(!online){publish("Sem rede. Consulte o cache; edição exige carregar o cadastro atual da API.");return true;}
        int id;xSemaphoreTake(mutex,portMAX_DELAY);id=view.selected.id;xSemaphoreGive(mutex);
        static char data[8193];char url[80];snprintf(url,sizeof(url),"/api/v1/products/%d",id);
        int status=transport("GET",url,nullptr,data,sizeof(data));if(status!=200){publish(error_text(status,data));return true;}
        auto* object=cJSON_Parse(data);static Product current;bool valid=decode(object,current);cJSON_Delete(object);
        if(!valid){publish("Cadastro da API inválido. Nenhuma edição iniciada.");return true;}
        xSemaphoreTake(mutex,portMAX_DELAY);view.selected=current;xSemaphoreGive(mutex);
    }
    if(cmd.action==Action::New || cmd.action==Action::Edit){bool allowed=has_module_permission(permissions,cmd.action==Action::New?"products.create":"products.update");if(!allowed){publish("Sem permissão para cadastrar ou editar.");return true;}xSemaphoreTake(mutex,portMAX_DELAY);if(cmd.action==Action::New)view.selected=Product{};view.mode=Mode::Form;xSemaphoreGive(mutex);publish("Preencha os campos. Preços: use vírgula ou ponto, sem separador de milhar.");return true;}
    if(cmd.action==Action::Confirm){if(!has_module_permission(permissions,"products.delete")){publish("Sem permissão para inativar.");return true;}xSemaphoreTake(mutex,portMAX_DELAY);view.mode=Mode::Confirm;xSemaphoreGive(mutex);publish("Confirma inativar este produto? O cadastro e histórico serão preservados.");return true;}
    if(cmd.action==Action::Save){xSemaphoreTake(mutex,portMAX_DELAY);view.selected=cmd.product;xSemaphoreGive(mutex);}
    if(!online){publish("Sem rede. Cadastro e edição exigem confirmação da API.");return true;}
    static char response[8193];char url[180];int code=0;
    if(cmd.action==Action::Save){if(!has_module_permission(permissions,cmd.product.id?"products.update":"products.create")){publish("Sem permissão para salvar.");return true;}
        auto* body=cJSON_CreateObject();for(unsigned i=0;i<field_count;++i){char* value=field(cmd.product,i);if(i>=6&&i<=10)for(char* c=value;*c;++c)if(*c==',')*c='.';
            if(i==13){if(value[0]){char* end=nullptr;long n=strtol(value,&end,10);if(!end||*end){cJSON_Delete(body);publish("Origem deve ser um número de 0 a 8.");return true;}cJSON_AddNumberToObject(body,keys[i],n);}else cJSON_AddNullToObject(body,keys[i]);}
            else if((i==1||i==10||i==11||i==12)&&!value[0])cJSON_AddNullToObject(body,keys[i]);else cJSON_AddStringToObject(body,keys[i],value);}
        cJSON_AddBoolToObject(body,"active",cmd.product.active);if(cmd.product.id)cJSON_AddNumberToObject(body,"version",cmd.product.version);
        char* payload=cJSON_PrintUnformatted(body);cJSON_Delete(body);if(!payload){publish("Memória insuficiente para salvar.");return true;}
        if(cmd.product.id)snprintf(url,sizeof(url),"/api/v1/products/%d",cmd.product.id);else snprintf(url,sizeof(url),"/api/v1/products");
        code=transport(cmd.product.id?"PUT":"POST",url,payload,response,sizeof(response));cJSON_free(payload);
        if(code!=200&&code!=201){publish(error_text(code,response));return true;}
        auto* data=cJSON_Parse(response);static Product saved;if(!decode(data,saved)){cJSON_Delete(data);publish("API confirmou gravação; resposta inválida. Atualize antes de repetir.");return true;}cJSON_Delete(data);xSemaphoreTake(mutex,portMAX_DELAY);view.selected=saved;view.mode=Mode::Detail;xSemaphoreGive(mutex);
    }else if(cmd.action==Action::Deactivate){if(!has_module_permission(permissions,"products.delete")){publish("Sem permissão para inativar.");return true;}int id,version;xSemaphoreTake(mutex,portMAX_DELAY);id=view.selected.id;version=view.selected.version;xSemaphoreGive(mutex);
        snprintf(url,sizeof(url),"/api/v1/products/%d?version=%d",id,version);code=transport("DELETE",url,nullptr,response,sizeof(response));if(code!=204){publish(error_text(code,response));return true;}
        xSemaphoreTake(mutex,portMAX_DELAY);view.selected.active=false;++view.selected.version;view.mode=Mode::Detail;xSemaphoreGive(mutex);
    }
    bool cached=sync_cache(path,transport);if(cached)cleanup_legacy_cache(api);publish(cached?"Operação confirmada pela API. Cache atualizado.":"Operação confirmada pela API. Cache anterior preservado; atualize o cache.");return true;
}
bool offline_product_get(int id,char* output,size_t capacity){auto path=usable_cache(cache_path(nullptr));if(path.empty())return false;CatalogFile file;if(!file.read(path))return false;static char row[6002];bool found=false;int rc;while((rc=file.next(row,sizeof(row)))>0){auto* j=cJSON_Parse(row);if(number(j,"id")==id&&strlen(row)<capacity){snprintf(output,capacity,"%s",row);found=true;}cJSON_Delete(j);}return rc==0&&found;}
bool offline_product_search(const char* query,unsigned after,char* output,size_t capacity){auto path=usable_cache(cache_path(nullptr));if(path.empty())return false;CatalogFile file;if(!file.read(path))return false;auto* result=cJSON_CreateObject();auto* items=cJSON_AddArrayToObject(result,"items");static char row[6002];auto search=folded(query);unsigned count=0,last=0,next=0;int rc;while((rc=file.next(row,sizeof(row)))>0){auto* j=cJSON_Parse(row);unsigned id=number(j,"id");if(id>after&&cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(j,"active"))&&(search.empty()||folded(json_text(j,"name")).find(search)!=std::string::npos||folded(json_text(j,"sku")).find(search)!=std::string::npos||search==json_text(j,"barcode"))){if(count<8){auto* item=cJSON_CreateObject();cJSON_AddNumberToObject(item,"id",id);cJSON_AddStringToObject(item,"name",json_text(j,"name"));cJSON_AddStringToObject(item,"sale_price",json_text(j,"sale_price"));cJSON_AddItemToArray(items,item);last=id;}else next=last;++count;}cJSON_Delete(j);}if(next)cJSON_AddNumberToObject(result,"next_id",next);else cJSON_AddNullToObject(result,"next_id");char* raw=cJSON_PrintUnformatted(result);bool ok=rc==0&&raw&&strlen(raw)<capacity;if(ok)snprintf(output,capacity,"%s",raw);cJSON_free(raw);cJSON_Delete(result);return ok;}
} // namespace tab5
