#include "../core/money.hpp"
#include <cassert>
#include <cstring>
int main(){using namespace tab5::money;int64_t value=0;assert(parse("190,00",2,value)&&value==19000);assert(!parse("1.234,56",2,value));assert(!parse("-1",2,value));assert(!parse("99999999999999999999999",2,value));assert(!parse("1.001",2,value));assert(line(12345,2500,value)&&value==30863);assert(line(19000,1000,value)&&value==19000);assert(!line(INT64_MAX,1000000,value));assert(percent(19000,1000)==1900);char text[32];format(text,sizeof(text),19000);assert(!strcmp(text,"190.00"));}
