#include "dashboard.hpp"
#include "erp_fonts.h"
#include "module_policy.hpp"
#include <cstring>
#include <cstdint>
#include <initializer_list>
#include <cstdio>

namespace tab5 {
namespace {
lv_obj_t *root, *content, *title, *body, *status, *identity_label, *notice_label;
lv_obj_t* controls[16]{};
unsigned count=0;
lv_group_t* group;
DashboardCallback callback;
bool light_theme=false;
const char* names[]={"Início", "Produtos", "Clientes / fornecedores", "Vendas / PDV", "Estoque", "Caixa / Financeiro", "Relatórios", "Minha sessão"};
const char* required[]={nullptr,"products.read","customers.read","sales.read","inventory.read","cash.open","reports.read",nullptr};
bool allowed[8]{};
char session_identity[1536]{};

void home(){
    lv_label_set_text(title,"Visão geral");
    lv_label_set_text(body,"Bem-vindo ao TAB5 ERP\n\nEscolha um módulo no menu lateral.\n\n"
        "Produtos, clientes, fornecedores e PDV disponíveis. Estoque, caixa e financeiro disponíveis. Relatórios disponíveis.\n\n"
        "Sua conexão e sessão podem ser acompanhadas nesta tela.\n"
        "Catálogo de produtos: atualize o cache dentro do módulo Produtos.\n\n"
        "Teclado: Tab / Shift+Tab navegam; Enter seleciona; Esc volta ao início.");
}
void key_event(lv_event_t* event){
    auto key=lv_event_get_key(event);
    if(key==LV_KEY_ESC)home();
    else if(key==LV_KEY_UP || key==LV_KEY_LEFT)lv_group_focus_prev(group);
    else if(key==LV_KEY_DOWN || key==LV_KEY_RIGHT)lv_group_focus_next(group);
}
void module_event(lv_event_t* event){
    unsigned index=static_cast<unsigned>(reinterpret_cast<uintptr_t>(lv_event_get_user_data(event)));
    if(!index){home();return;}
    if(index==6 && allowed[index]){callback(DashboardAction::Reports);return;}
    if(index==5 && allowed[index]){callback(DashboardAction::Cash);return;}
    if(index==4 && allowed[index]){callback(DashboardAction::Inventory);return;}
    if(index==3 && allowed[index]){callback(DashboardAction::Sales);return;}
    if(index==2 && allowed[index]){callback(DashboardAction::Customers);return;}
    if(index==1 && allowed[index]){callback(DashboardAction::Products);return;}
    lv_label_set_text(title,names[index]);
    lv_label_set_text(body,index==7?session_identity:allowed[index]?
        "Este módulo ainda não está disponível.\n\nUse o menu para voltar ao início ou acessar sua sessão.":
        "Seu perfil não tem permissão para acessar este módulo.\n\nSolicite acesso ao administrador ERP.");
}
void action_event(lv_event_t* event){callback(static_cast<DashboardAction>(reinterpret_cast<uintptr_t>(lv_event_get_user_data(event))));}
lv_obj_t* button(lv_obj_t* parent,const char* caption,int x,int y,int width){
    auto* obj=lv_button_create(parent);lv_obj_set_pos(obj,x,y);lv_obj_set_size(obj,width,48);
    auto* label=lv_label_create(obj);lv_label_set_text(label,caption);lv_obj_center(label);
    lv_obj_add_event_cb(obj,key_event,LV_EVENT_KEY,nullptr);
    controls[count++]=obj;lv_group_add_obj(group,obj);return obj;
}
void apply_theme(bool light){
    light_theme=light;
    const auto background=lv_color_hex(light?0xf1f5f9:0x111827);
    const auto foreground=lv_color_hex(light?0x0f172a:0xf8fafc);
    lv_obj_set_style_bg_color(root,background,0);lv_obj_set_style_text_color(root,foreground,0);
    lv_obj_set_style_bg_color(content,lv_color_hex(light?0xffffff:0x1e293b),0);
    for(auto* label:{title,body,status,identity_label,notice_label})lv_obj_set_style_text_color(label,foreground,0);
    for(unsigned i=0;i<count;++i){
        lv_obj_set_style_bg_color(controls[i],lv_color_hex(light?0xcbd5e1:0x334155),0);
        lv_obj_set_style_border_width(controls[i],2,LV_STATE_FOCUSED);
        lv_obj_set_style_border_color(controls[i],lv_color_hex(light?0x2563eb:0x93c5fd),LV_STATE_FOCUSED);
        lv_obj_set_style_text_color(lv_obj_get_child(controls[i],0),foreground,0);
    }
}
}
void dashboard_create(lv_display_t* display,DashboardCallback cb){
    callback=cb;group=lv_group_create();
    root=lv_obj_create(lv_display_get_screen_active(display));lv_obj_set_pos(root,0,0);lv_obj_set_size(root,1280,720);
    lv_obj_remove_flag(root,LV_OBJ_FLAG_SCROLLABLE);lv_obj_set_style_pad_all(root,16,0);
    identity_label=lv_label_create(root);lv_obj_set_pos(identity_label,12,8);lv_obj_set_style_text_font(identity_label,&erp_font_pt_28,0);
    lv_label_set_text(identity_label,"TAB5 ERP | Menu principal");
    status=lv_label_create(root);lv_obj_set_pos(status,12,54);lv_obj_set_width(status,1210);
    for(unsigned i=0;i<8;++i){auto* obj=button(root,names[i],12,98+i*53,230);lv_obj_add_event_cb(obj,module_event,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(i)));}
    content=lv_obj_create(root);lv_obj_set_pos(content,264,104);lv_obj_set_size(content,946,442);
    title=lv_label_create(content);lv_obj_set_pos(title,4,4);lv_obj_set_style_text_font(title,&erp_font_pt_28,0);
    body=lv_label_create(content);lv_obj_set_pos(body,4,54);lv_obj_set_width(body,886);lv_label_set_long_mode(body,LV_LABEL_LONG_WRAP);
    notice_label=lv_label_create(root);lv_obj_set_pos(notice_label,264,552);lv_obj_set_width(notice_label,946);lv_label_set_text(notice_label,"");
    const char* actions[]={"Rede / servidor","Senha ERP","Trocar tema","Bloquear","Sair"};
    const DashboardAction codes[]={DashboardAction::Network,DashboardAction::Password,DashboardAction::Theme,DashboardAction::Lock,DashboardAction::Logout};
    for(unsigned i=0;i<5;++i){auto* obj=button(root,actions[i],12+i*244,588,230);lv_obj_add_event_cb(obj,action_event,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(codes[i])));}
    auto* hint=lv_label_create(root);lv_obj_set_pos(hint,12,656);lv_label_set_text(hint,"TAB5 ERP v0.10.0 | Configurações no microSD | pt-BR");
    home();apply_theme(false);lv_obj_add_flag(root,LV_OBJ_FLAG_HIDDEN);
}
void dashboard_show(const char* identity,const char* permissions,bool light,const char* notice){
    const bool hidden=lv_obj_has_flag(root,LV_OBJ_FLAG_HIDDEN);
    snprintf(session_identity,sizeof(session_identity),"%s",identity);
    for(unsigned i=0;i<8;++i){allowed[i]=has_module_permission(permissions,required[i]);}
    allowed[5]=has_module_permission(permissions,"cash.open")||has_module_permission(permissions,"cash.close")||has_module_permission(permissions,"cash.deposit")||has_module_permission(permissions,"cash.withdraw")||has_module_permission(permissions,"reports.financial");
    allowed[2]=has_module_permission(permissions,"customers.read")||has_module_permission(permissions,"suppliers.read");
    lv_label_set_text(notice_label,notice);
    apply_theme(light);lv_obj_remove_flag(root,LV_OBJ_FLAG_HIDDEN);
    lv_group_set_default(group);
    for(auto* input=lv_indev_get_next(nullptr);input;input=lv_indev_get_next(input))if(lv_indev_get_type(input)==LV_INDEV_TYPE_KEYPAD)lv_indev_set_group(input,group);
    if(hidden){home();lv_group_focus_obj(controls[0]);}
}
void dashboard_hide(){if(root)lv_obj_add_flag(root,LV_OBJ_FLAG_HIDDEN);}
void dashboard_status(bool wifi,bool api,bool busy,bool light){
    char value[256];snprintf(value,sizeof(value),"Wi-Fi: %s   |   API: %s   |   Sessão autenticada   |   %s",
        wifi?"conectado":"desconectado",api&&wifi?"disponível":"sem confirmação",busy?"Comunicando...":"Pronto");
    lv_label_set_text(status,value);if(light!=light_theme)apply_theme(light);
    for(unsigned i=8;i<count;++i){if(busy)lv_obj_add_state(controls[i],LV_STATE_DISABLED);else lv_obj_remove_state(controls[i],LV_STATE_DISABLED);}
}
}
