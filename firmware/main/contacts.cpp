#include "contacts.hpp"
#include "module_policy.hpp"
#include "erp_fonts.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "cJSON.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include <atomic>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <new>
#include <string>

namespace tab5 { namespace {
constexpr unsigned fields_count=12, page_size=8;
const char* keys[]={"name","person_type","document","trade_name","phone","email","address","city","state","postal_code","contact_name","notes"};
const char* labels[]={"Nome / razão social *","Tipo PF ou PJ *","CPF/CNPJ (opcional)","Nome fantasia","Telefone","E-mail","Endereço","Cidade","UF","CEP","Contato","Observações"};
const unsigned limits[]={120,2,18,120,32,160,200,80,2,9,120,500};
enum class Mode {List,Detail,Form,Confirm,History,Links};
enum class Action {Browse,Get,New,Edit,Save,Confirm,Disable,History,Links,Associate,Remove};
struct Record {int id,version;bool active,document_editable;char fields[fields_count][2001];char created[40],updated[40];};
struct Row {int id;char text[600];};
struct State {unsigned serial,after,next;Mode mode;bool busy,supplier;unsigned count;Row rows[page_size];Record record;char message[300];};
struct Command {Action action;unsigned generation,after;int id,product;bool supplier,inactive;char query[481],document[19];};
struct Workspace {State state,draw;Record draft,working;Command command;char response[16385];char permissions[2048];};
Workspace* w;SemaphoreHandle_t mutex;QueueHandle_t queue;
std::atomic<unsigned> generation{0};std::atomic<bool> visible{false};
lv_obj_t *root,*heading,*message,*query,*document_filter,*inactive,*form,*active,*keyboard,*inputs[fields_count],*rows[page_size],*buttons[7];
lv_group_t* group;void (*home_callback)();bool light=false;unsigned drawn=0;
bool permission(const char* permissions,const char* module,const char* action){char code[80];snprintf(code,sizeof(code),"%s.%s",module,action);return has_module_permission(permissions,code);}
const char* module(bool supplier){return supplier?"suppliers":"customers";}
template<class F> void update_current(const Command& cmd,F apply){xSemaphoreTake(mutex,portMAX_DELAY);if(cmd.generation==generation.load())apply();xSemaphoreGive(mutex);}
void publish(const Command& cmd,const char* text){update_current(cmd,[&]{w->state.busy=false;snprintf(w->state.message,sizeof(w->state.message),"%s",text);++w->state.serial;});}
const char* text(cJSON* object,const char* name){auto* v=cJSON_GetObjectItemCaseSensitive(object,name);return cJSON_IsString(v)?v->valuestring:"";}
int number(cJSON* object,const char* name){auto* v=cJSON_GetObjectItemCaseSensitive(object,name);return cJSON_IsNumber(v)?v->valueint:0;}
const char* error(int code,cJSON* data){const char* detail=text(cJSON_GetObjectItemCaseSensitive(data,"error"),"message");if(*detail)return detail;return code<=0?"Sem resposta da API. Confira a conexão.":code==403?"Seu perfil não permite esta operação.":code==401?"Sessão expirada. Entre novamente.":code==409?"Cadastro alterado ou documento duplicado. Consulte novamente.":"Não foi possível concluir a operação.";}
bool decode(cJSON* data,Record& out){memset(&out,0,sizeof(out));out.id=number(data,"id");out.version=number(data,"version");out.active=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(data,"active"));out.document_editable=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(data,"document_editable"));for(unsigned i=0;i<fields_count;++i){const char* value=text(data,keys[i]);if(strlen(value)>=sizeof(out.fields[i]))return false;snprintf(out.fields[i],sizeof(out.fields[i]),"%s",value);}snprintf(out.created,sizeof(out.created),"%s",text(data,"created_at"));snprintf(out.updated,sizeof(out.updated),"%s",text(data,"updated_at"));return out.id>0&&out.version>0&&out.fields[0][0];}
void clear_form(){for(auto* input:inputs)lv_textarea_set_text(input,"");lv_textarea_set_text(query,"");lv_textarea_set_text(document_filter,"");for(auto* row:rows)lv_label_set_text(lv_obj_get_child(row,0),"");lv_label_set_text(message,"");}
void enqueue(Action action,int id=0,unsigned after=0){
    if(!visible)return;
    Command cmd{};cmd.action=action;cmd.id=id;cmd.after=after;cmd.generation=generation.load();
    xSemaphoreTake(mutex,portMAX_DELAY);
    if(w->state.busy){xSemaphoreGive(mutex);return;}
    cmd.supplier=w->state.supplier;cmd.inactive=lv_obj_has_state(inactive,LV_STATE_CHECKED);
    snprintf(cmd.query,sizeof(cmd.query),"%s",lv_textarea_get_text(query));snprintf(cmd.document,sizeof(cmd.document),"%s",lv_textarea_get_text(document_filter));
    if(!id)cmd.id=w->state.record.id;
    w->draft=w->state.record;
    if(action==Action::Save){for(unsigned i=0;i<fields_count;++i)snprintf(w->draft.fields[i],sizeof(w->draft.fields[i]),"%s",lv_textarea_get_text(inputs[i]));w->draft.active=lv_obj_has_state(active,LV_STATE_CHECKED);w->state.record=w->draft;}
    if(action==Action::Associate||action==Action::Remove){char* end=nullptr;long value=strtol(cmd.query,&end,10);if(!cmd.query[0]||*end||value<=0||value>2147483647){xSemaphoreGive(mutex);lv_label_set_text(message,"Informe o ID inteiro do produto.");return;}cmd.product=value;}
    if(xQueueSend(queue,&cmd,0)==pdTRUE){w->state.busy=true;snprintf(w->state.message,sizeof(w->state.message),"Aguarde...");++w->state.serial;}
    xSemaphoreGive(mutex);
}
void row_event(lv_event_t* e){enqueue(Action::Get,static_cast<int>(reinterpret_cast<intptr_t>(lv_event_get_user_data(e))));}
void keyboard_target(lv_event_t* e){lv_keyboard_set_textarea(keyboard,lv_event_get_target_obj(e));if(lv_event_get_code(e)==LV_EVENT_CLICKED)lv_obj_remove_flag(keyboard,LV_OBJ_FLAG_HIDDEN);}
void button_event(lv_event_t* e){unsigned i=reinterpret_cast<uintptr_t>(lv_event_get_user_data(e));if(i==6){contacts_hide();home_callback();return;}
    xSemaphoreTake(mutex,portMAX_DELAY);Mode mode=w->state.mode;unsigned next=w->state.next;bool busy=w->state.busy;xSemaphoreGive(mutex);if(busy)return;
    if(mode==Mode::List){if(i==0)enqueue(Action::Browse);if(i==1)enqueue(Action::Browse,0,next);if(i==2)enqueue(Action::New);if(i==3)enqueue(Action::Browse);if(i==4){bool supplier=w->draw.supplier;contacts_open(w->permissions,light,!supplier);}}
    else if(mode==Mode::Form){if(i==0)enqueue(Action::Save);if(i==1){if(w->draw.record.id)enqueue(Action::Get,w->draw.record.id);else enqueue(Action::Browse);}}
    else if(mode==Mode::Detail){if(i==0)enqueue(Action::Edit);if(i==1)enqueue(Action::Confirm);if(i==2)enqueue(Action::History);if(i==3)enqueue(Action::Browse);if(i==4)enqueue(Action::Links);}
    else if(mode==Mode::Confirm){if(i==0)enqueue(Action::Disable);if(i==1)enqueue(Action::Get);}
    else{if(i==0)enqueue(mode==Mode::History?Action::History:Action::Links,0,next);if(i==1)enqueue(Action::Get);if(mode==Mode::Links&&i==2)enqueue(Action::Associate);if(mode==Mode::Links&&i==3)enqueue(Action::Remove);}
}
void key_event(lv_event_t* e){auto key=lv_event_get_key(e);if(key==LV_KEY_ESC){contacts_hide();home_callback();}else if(key==LV_KEY_UP||key==LV_KEY_LEFT)lv_group_focus_prev(group);else if(key==LV_KEY_DOWN||key==LV_KEY_RIGHT)lv_group_focus_next(group);}
void render(lv_timer_t*){
    if(!visible)return;
    xSemaphoreTake(mutex,portMAX_DELAY);w->draw=w->state;xSemaphoreGive(mutex);auto& state=w->draw;if(state.serial==drawn)return;drawn=state.serial;
    const char* mod=module(state.supplier);char title[160];snprintf(title,sizeof(title),"%s | %s | ID %d",state.supplier?"Fornecedores":"Clientes",state.mode==Mode::List?"Pesquisa":state.mode==Mode::Form?"Cadastro / edição":state.mode==Mode::History?"Histórico":state.mode==Mode::Links?"Produtos vinculados":"Consulta",state.record.id);lv_label_set_text(heading,title);lv_label_set_text(message,state.message);
    lv_group_remove_all_objs(group);lv_group_set_default(group);for(auto* indev=lv_indev_get_next(nullptr);indev;indev=lv_indev_get_next(indev))if(lv_indev_get_type(indev)==LV_INDEV_TYPE_KEYPAD)lv_indev_set_group(indev,group);
    bool listing=state.mode==Mode::List,editing=state.mode==Mode::Form,detail=state.mode==Mode::Detail||editing||state.mode==Mode::Confirm;
    for(auto* obj:{query,document_filter,inactive})lv_obj_add_flag(obj,LV_OBJ_FLAG_HIDDEN);
    if(listing||state.mode==Mode::Links){lv_obj_remove_flag(query,LV_OBJ_FLAG_HIDDEN);lv_textarea_set_placeholder_text(query,listing?"Pesquisar nome":"ID do produto para vínculo");lv_group_add_obj(group,query);}
    if(listing){lv_obj_remove_flag(inactive,LV_OBJ_FLAG_HIDDEN);lv_group_add_obj(group,inactive);if(permission(w->permissions,mod,"documents")){lv_obj_remove_flag(document_filter,LV_OBJ_FLAG_HIDDEN);lv_group_add_obj(group,document_filter);}}
    if(detail){lv_obj_remove_flag(form,LV_OBJ_FLAG_HIDDEN);lv_obj_set_height(form,editing?250:400);for(unsigned i=0;i<fields_count;++i){lv_textarea_set_text(inputs[i],state.record.fields[i]);bool enabled=editing&&(i!=2||permission(w->permissions,mod,"documents"))&&(i!=1||permission(w->permissions,mod,"documents")||!state.record.id);if(enabled){lv_obj_remove_state(inputs[i],LV_STATE_DISABLED);lv_group_add_obj(group,inputs[i]);}else lv_obj_add_state(inputs[i],LV_STATE_DISABLED);}if(state.record.active)lv_obj_add_state(active,LV_STATE_CHECKED);else lv_obj_remove_state(active,LV_STATE_CHECKED);if(editing){lv_obj_remove_state(active,LV_STATE_DISABLED);lv_group_add_obj(group,active);}else lv_obj_add_state(active,LV_STATE_DISABLED);}
    else lv_obj_add_flag(form,LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(keyboard,LV_OBJ_FLAG_HIDDEN);if(editing){lv_obj_remove_flag(keyboard,LV_OBJ_FLAG_HIDDEN);lv_keyboard_set_textarea(keyboard,inputs[0]);}
    for(unsigned i=0;i<page_size;++i){lv_obj_add_flag(rows[i],LV_OBJ_FLAG_HIDDEN);lv_obj_remove_event_cb(rows[i],row_event);if(!detail&&i<state.count){lv_obj_remove_flag(rows[i],LV_OBJ_FLAG_HIDDEN);lv_label_set_text(lv_obj_get_child(rows[i],0),state.rows[i].text);if(listing){lv_obj_add_event_cb(rows[i],row_event,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<intptr_t>(state.rows[i].id)));lv_group_add_obj(group,rows[i]);}}}
    const char* captions[7]={"","","","","","","Menu"};
    if(listing){captions[0]="Primeira página";captions[1]="Próxima";captions[2]="Novo";captions[3]="Pesquisar";captions[4]=state.supplier?"Clientes":"Fornecedores";}
    else if(editing){captions[0]="Salvar";captions[1]="Cancelar";}
    else if(state.mode==Mode::Detail){captions[0]="Editar";captions[1]="Inativar";captions[2]="Histórico";captions[3]="Voltar";if(state.supplier)captions[4]="Produtos";}
    else if(state.mode==Mode::Confirm){captions[0]="Confirmar";captions[1]="Cancelar";}
    else{captions[0]="Próxima";captions[1]="Voltar";if(state.mode==Mode::Links){captions[2]="Vincular";captions[3]="Remover vínculo";}}
    for(unsigned i=0;i<7;++i){bool show=*captions[i];if(listing&&i==2&&!permission(w->permissions,mod,"create"))show=false;if(listing&&i==4&&!permission(w->permissions,module(!state.supplier),"read"))show=false;if(state.mode==Mode::Detail&&((i==0&&!permission(w->permissions,mod,"update"))||(i==1&&(!state.record.active||!permission(w->permissions,mod,"delete")))))show=false;if(state.mode==Mode::Links&&(i==2||i==3)&&!permission(w->permissions,mod,"update"))show=false;
        lv_label_set_text(lv_obj_get_child(buttons[i],0),captions[i]);lv_obj_center(lv_obj_get_child(buttons[i],0));lv_obj_set_y(buttons[i],editing?380:568);if(show){lv_obj_remove_flag(buttons[i],LV_OBJ_FLAG_HIDDEN);lv_group_add_obj(group,buttons[i]);}else lv_obj_add_flag(buttons[i],LV_OBJ_FLAG_HIDDEN);
        if((state.busy&&i!=6)||((listing||state.mode==Mode::History||state.mode==Mode::Links)&&i==(listing?1:0)&&!state.next))lv_obj_add_state(buttons[i],LV_STATE_DISABLED);else lv_obj_remove_state(buttons[i],LV_STATE_DISABLED);}
}
} // namespace
void contacts_create(lv_display_t* display,void (*home)()){
    auto* memory=heap_caps_malloc(sizeof(Workspace),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);if(!memory){ESP_LOGE("contacts","PSRAM indisponível");return;}w=new(memory)Workspace{};mutex=xSemaphoreCreateMutex();queue=xQueueCreate(1,sizeof(Command));home_callback=home;group=lv_group_create();
    root=lv_obj_create(lv_display_get_screen_active(display));lv_obj_set_pos(root,0,0);lv_obj_set_size(root,1280,720);lv_obj_set_style_pad_all(root,12,0);lv_obj_remove_flag(root,LV_OBJ_FLAG_SCROLLABLE);
    heading=lv_label_create(root);lv_obj_set_pos(heading,8,4);lv_obj_set_style_text_font(heading,&erp_font_pt_28,0);message=lv_label_create(root);lv_obj_set_pos(message,8,45);lv_obj_set_width(message,1200);
    query=lv_textarea_create(root);lv_obj_set_pos(query,8,104);lv_obj_set_size(query,450,50);lv_textarea_set_one_line(query,true);lv_textarea_set_max_length(query,120);
    document_filter=lv_textarea_create(root);lv_obj_set_pos(document_filter,480,104);lv_obj_set_size(document_filter,370,50);lv_textarea_set_one_line(document_filter,true);lv_textarea_set_max_length(document_filter,18);lv_textarea_set_placeholder_text(document_filter,"CPF/CNPJ exato (opcional)");
    inactive=lv_checkbox_create(root);lv_obj_set_pos(inactive,880,110);lv_checkbox_set_text(inactive,"Mostrar inativos");
    for(auto* obj:{query,document_filter}){lv_obj_add_event_cb(obj,keyboard_target,LV_EVENT_FOCUSED,nullptr);lv_obj_add_event_cb(obj,keyboard_target,LV_EVENT_CLICKED,nullptr);}
    for(unsigned i=0;i<page_size;++i){rows[i]=lv_button_create(root);lv_obj_set_pos(rows[i],8,170+i*46);lv_obj_set_size(rows[i],1204,42);auto* label=lv_label_create(rows[i]);lv_obj_set_width(label,1160);lv_label_set_long_mode(label,LV_LABEL_LONG_DOT);lv_obj_center(label);lv_obj_add_event_cb(rows[i],key_event,LV_EVENT_KEY,nullptr);}
    form=lv_obj_create(root);lv_obj_set_pos(form,8,104);lv_obj_set_size(form,1204,250);lv_obj_set_style_pad_all(form,8,0);
    for(unsigned i=0;i<fields_count;++i){auto* label=lv_label_create(form);lv_label_set_text(label,labels[i]);lv_obj_set_pos(label,(i%3)*390,(i/3)*88);inputs[i]=lv_textarea_create(form);lv_obj_set_pos(inputs[i],(i%3)*390,(i/3)*88+28);lv_obj_set_size(inputs[i],374,48);lv_textarea_set_one_line(inputs[i],true);lv_textarea_set_max_length(inputs[i],limits[i]);lv_obj_add_event_cb(inputs[i],keyboard_target,LV_EVENT_FOCUSED,nullptr);lv_obj_add_event_cb(inputs[i],keyboard_target,LV_EVENT_CLICKED,nullptr);}
    active=lv_checkbox_create(form);lv_obj_set_pos(active,8,366);lv_checkbox_set_text(active,"Ativo");
    for(unsigned i=0;i<7;++i){buttons[i]=lv_button_create(root);lv_obj_set_pos(buttons[i],8+i*172,568);lv_obj_set_size(buttons[i],164,48);lv_label_create(buttons[i]);lv_obj_add_event_cb(buttons[i],button_event,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(i)));lv_obj_add_event_cb(buttons[i],key_event,LV_EVENT_KEY,nullptr);}
    keyboard=lv_keyboard_create(root);lv_obj_set_pos(keyboard,8,436);lv_obj_set_size(keyboard,1204,240);lv_obj_add_flag(keyboard,LV_OBJ_FLAG_HIDDEN);for(auto event:{LV_EVENT_READY,LV_EVENT_CANCEL})lv_obj_add_event_cb(keyboard,[](lv_event_t*){lv_obj_add_flag(keyboard,LV_OBJ_FLAG_HIDDEN);},event,nullptr);
    lv_obj_add_flag(root,LV_OBJ_FLAG_HIDDEN);lv_timer_create(render,100,nullptr);
}
void contacts_hide(){if(!w||!visible)return;visible=false;++generation;xQueueReset(queue);lv_obj_add_flag(root,LV_OBJ_FLAG_HIDDEN);clear_form();xSemaphoreTake(mutex,portMAX_DELAY);memset(&w->state,0,sizeof(w->state));memset(&w->draw,0,sizeof(w->draw));memset(&w->draft,0,sizeof(w->draft));xSemaphoreGive(mutex);}
void contacts_open(const char* permissions,bool light_value,bool supplier){if(!w)return;char copied[2048];snprintf(copied,sizeof(copied),"%s",permissions);if(!permission(copied,module(supplier),"read")){contacts_hide();home_callback();return;}contacts_hide();snprintf(w->permissions,sizeof(w->permissions),"%s",copied);light=light_value;drawn=0;xSemaphoreTake(mutex,portMAX_DELAY);memset(&w->state,0,sizeof(w->state));w->state.supplier=supplier;xSemaphoreGive(mutex);lv_obj_set_style_bg_color(root,lv_color_hex(light?0xf1f5f9:0x111827),0);lv_obj_set_style_bg_color(form,lv_color_hex(light?0xffffff:0x1e293b),0);lv_obj_set_style_text_color(form,lv_color_hex(light?0x0f172a:0xf8fafc),0);
    for(auto* obj:{heading,message})lv_obj_set_style_text_color(obj,lv_color_hex(light?0x0f172a:0xf8fafc),0);
    for(auto* obj:inputs){lv_obj_set_style_bg_color(obj,lv_color_hex(light?0xe2e8f0:0x334155),0);lv_obj_set_style_text_color(obj,lv_color_hex(light?0x0f172a:0xf8fafc),0);}
    for(auto* obj:{query,document_filter}){lv_obj_set_style_bg_color(obj,lv_color_hex(light?0xe2e8f0:0x334155),0);lv_obj_set_style_text_color(obj,lv_color_hex(light?0x0f172a:0xf8fafc),0);}
    for(auto* obj:buttons){lv_obj_set_style_bg_color(obj,lv_color_hex(light?0xe2e8f0:0x334155),0);lv_obj_set_style_text_color(obj,lv_color_hex(light?0x0f172a:0xf8fafc),0);}
    for(auto* obj:rows){lv_obj_set_style_bg_color(obj,lv_color_hex(light?0xe2e8f0:0x334155),0);lv_obj_set_style_text_color(obj,lv_color_hex(light?0x0f172a:0xf8fafc),0);}
    lv_obj_set_style_text_color(inactive,lv_color_hex(light?0x0f172a:0xf8fafc),0);lv_obj_set_style_text_color(active,lv_color_hex(light?0x0f172a:0xf8fafc),0);lv_obj_set_style_text_color(keyboard,lv_color_hex(light?0x0f172a:0xf8fafc),LV_PART_ITEMS);lv_obj_set_style_bg_color(keyboard,lv_color_hex(light?0xe2e8f0:0x334155),LV_PART_ITEMS);
    visible=true;lv_obj_remove_flag(root,LV_OBJ_FLAG_HIDDEN);enqueue(Action::Browse);render(nullptr);
}
bool contacts_handle_next(const char* permissions,bool online,ProductTransport transport){
    if(!w||xQueueReceive(queue,&w->command,0)!=pdTRUE)return false;
    const Command cmd=w->command;if(cmd.generation!=generation.load())return true;
    xSemaphoreTake(mutex,portMAX_DELAY);w->working=w->draft;xSemaphoreGive(mutex);
    const char* mod=module(cmd.supplier);const char* needed=cmd.action==Action::New||(cmd.action==Action::Save&&w->working.id==0)?"create":cmd.action==Action::Edit||cmd.action==Action::Save||cmd.action==Action::Associate||cmd.action==Action::Remove?"update":cmd.action==Action::Disable||cmd.action==Action::Confirm?"delete":"read";
    if(!permission(permissions,mod,needed)){publish(cmd,"Seu perfil não permite esta operação.");memset(&w->working,0,sizeof(w->working));return true;}
    if(!online){publish(cmd,"Sem rede. Dados pessoais exigem consulta online; nada é salvo no cartão.");memset(&w->working,0,sizeof(w->working));return true;}
    if(cmd.action==Action::New){update_current(cmd,[&]{memset(&w->state.record,0,sizeof(w->state.record));w->state.record.active=true;snprintf(w->state.record.fields[1],2001,"%s",cmd.supplier?"PJ":"PF");w->state.mode=Mode::Form;});publish(cmd,"Documento opcional. Informe apenas os dados necessários.");memset(&w->working,0,sizeof(w->working));return true;}
    if(cmd.action==Action::Confirm){update_current(cmd,[&]{w->state.mode=Mode::Confirm;});publish(cmd,"Confirma inativar? Cadastro e histórico serão preservados.");memset(&w->working,0,sizeof(w->working));return true;}
    char path[180];snprintf(path,sizeof(path),"/api/v1/%s/%d",mod,cmd.id);const char* method="GET";cJSON* body=nullptr;
    if(cmd.action==Action::Browse){snprintf(path,sizeof(path),"/api/v1/%s/search",mod);method="POST";body=cJSON_CreateObject();cJSON_AddStringToObject(body,"q",cmd.query);if(cmd.document[0])cJSON_AddStringToObject(body,"document_query",cmd.document);cJSON_AddNumberToObject(body,"after_id",cmd.after);cJSON_AddNumberToObject(body,"limit",8);cJSON_AddBoolToObject(body,"include_inactive",cmd.inactive);}
    if(cmd.action==Action::Save){method=w->working.id?"PUT":"POST";if(!w->working.id)snprintf(path,sizeof(path),"/api/v1/%s",mod);body=cJSON_CreateObject();for(unsigned i=0;i<fields_count;++i){if(i==2&&!w->working.fields[i][0])cJSON_AddNullToObject(body,keys[i]);else cJSON_AddStringToObject(body,keys[i],w->working.fields[i]);}cJSON_AddBoolToObject(body,"active",w->working.active);if(w->working.id)cJSON_AddNumberToObject(body,"version",w->working.version);}
    if(cmd.action==Action::Disable){method="DELETE";snprintf(path,sizeof(path),"/api/v1/%s/%d?version=%d",mod,cmd.id,w->working.version);}
    if(cmd.action==Action::History||cmd.action==Action::Links)snprintf(path,sizeof(path),"/api/v1/%s/%d/%s?after_id=%u&limit=8",mod,cmd.id,cmd.action==Action::History?"history":"products",cmd.after);
    if(cmd.action==Action::Associate||cmd.action==Action::Remove){snprintf(path,sizeof(path),"/api/v1/suppliers/%d/products",cmd.id);method=cmd.action==Action::Associate?"POST":"DELETE";if(cmd.action==Action::Associate){body=cJSON_CreateObject();cJSON_AddNumberToObject(body,"product_id",cmd.product);}else snprintf(path,sizeof(path),"/api/v1/suppliers/%d/products/%d",cmd.id,cmd.product);}
    char* raw=body?cJSON_PrintUnformatted(body):nullptr;int code=transport(method,path,raw,w->response,sizeof(w->response));cJSON_free(raw);cJSON_Delete(body);auto* data=cJSON_Parse(w->response);
    if(cmd.generation!=generation.load()){cJSON_Delete(data);memset(w->response,0,sizeof(w->response));memset(&w->working,0,sizeof(w->working));return true;}
    if(code<200||code>=300){if(cmd.action==Action::Save){update_current(cmd,[&]{w->state.record=w->working;});}publish(cmd,error(code,data));}
    else if(cmd.action==Action::Associate||cmd.action==Action::Remove){publish(cmd,"Vínculo atualizado. Volte à consulta e abra Produtos para atualizar a lista.");}
    else if(cmd.action==Action::Browse||cmd.action==Action::History||cmd.action==Action::Links){auto* items=cJSON_GetObjectItemCaseSensitive(data,"items");if(!cJSON_IsArray(items)||cJSON_GetArraySize(items)>8){publish(cmd,"Resposta inválida da API.");}else{update_current(cmd,[&]{w->state.count=0;w->state.after=cmd.after;w->state.next=number(data,"next_id");w->state.mode=cmd.action==Action::Browse?Mode::List:cmd.action==Action::History?Mode::History:Mode::Links;cJSON* item;cJSON_ArrayForEach(item,items){auto& row=w->state.rows[w->state.count++];row.id=number(item,"id");if(cmd.action==Action::History)snprintf(row.text,sizeof(row.text),"%s | %s",text(item,"created_at"),text(item,"operation"));else snprintf(row.text,sizeof(row.text),"ID %d | %s%s",row.id,text(item,"name"),cmd.action==Action::Browse&&!cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(item,"active"))?" | Inativo":"");}});publish(cmd,cmd.action==Action::History?"Alterações cadastrais. Compras serão disponibilizadas na etapa de vendas.":"Consulta online. Dados pessoais não são gravados no microSD.");}}
    else{if(!decode(data,w->working))publish(cmd,"Resposta de cadastro inválida.");else{update_current(cmd,[&]{w->state.record=w->working;w->state.mode=cmd.action==Action::Edit?Mode::Form:Mode::Detail;});char info[240];snprintf(info,sizeof(info),"Criado %s | Alterado %s | Versão %d%s",w->working.created,w->working.updated,w->working.version,w->working.document_editable?"":" | Documento restrito");publish(cmd,info);}}
    cJSON_Delete(data);memset(w->response,0,sizeof(w->response));memset(&w->working,0,sizeof(w->working));return true;
}
} // namespace tab5
