#include "../core/product_catalog.hpp"
#include <cassert>
#include <string>
int main(){
    using namespace tab5::catalog;
    assert(folded("CAFÉ SÃO JOÃO") == folded("café são joão"));
    assert(folded("Água").find(folded("ÁGUA")) != std::string::npos);
    const char* json=R"({"id":3,"version":2,"sku":"ABC","name":"Café","category":"Bebidas","description":"Descrição","unit":"UN","cost_price":"0.10","sale_price":"12.30","stock":"2.500","stock_min":"3.000","stock_max":null,"active":true,"origin":0})";
    auto* data=cJSON_Parse(json);Product p;
    assert(decode(data,p));assert(p.id==3&&p.version==2);
    assert(std::string(p.sale)=="12.30");assert(std::string(p.stock)=="2.500");
    assert(std::string(p.origin)=="0");assert(p.maximum[0]==0);
    cJSON_ReplaceItemInObject(data,"name",cJSON_CreateString(std::string(500,'x').c_str()));
    assert(!decode(data,p));cJSON_Delete(data);
    data=cJSON_Parse("{\"id\":0,\"sku\":\"ABC\",\"name\":\"X\"}");assert(!decode(data,p));cJSON_Delete(data);
}
