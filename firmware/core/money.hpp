#pragma once
#include <cstdint>
#include <cstdio>
#include <climits>
namespace tab5::money {
// Decimal input only: no floating-point or thousands separators.
inline bool parse(const char* s,unsigned decimals,int64_t& out) {
    if(!s || !*s || decimals>3) return false;
    int64_t whole=0,fraction=0,scale=1;
    unsigned count=0;
    bool dot=false,digit=false;
    for(const char* p=s;*p;++p) {
        if(*p=='.'||*p==',') {
            if(dot) return false;
            dot=true;
            continue;
        }
        if(*p<'0'||*p>'9') return false;
        digit=true;
        if(dot) {
            if(++count>decimals) return false;
            fraction=fraction*10+(*p-'0');
        } else {
            if(whole>(INT64_MAX-9)/10) return false;
            whole=whole*10+(*p-'0');
        }
    }
    if(!digit) return false;
    for(unsigned i=0;i<decimals;++i) scale*=10;
    for(unsigned i=count;i<decimals;++i) fraction*=10;
    if(whole>(INT64_MAX-fraction)/scale) return false;
    out=whole*scale+fraction;
    return true;
}
inline void format(char* out,size_t cap,int64_t value,unsigned decimals=2) {
    int64_t scale=1;
    for(unsigned i=0;i<decimals;++i) scale*=10;
    snprintf(out,cap,"%lld.%0*lld",static_cast<long long>(value/scale),int(decimals),static_cast<long long>(value%scale));
}
inline bool line(int64_t price,int64_t milli,int64_t& out) {
    if(price<0||milli<=0) return false;
    int64_t whole=milli/1000,remainder=milli%1000;
    if(whole&&price>INT64_MAX/whole) return false;
    int64_t main=price*whole;
    int64_t part=(price/1000)*remainder+((price%1000)*remainder+500)/1000;
    if(main>INT64_MAX-part) return false;
    out=main+part;
    return out<=99999999999999LL;
}
inline int64_t percent(int64_t cents,int64_t hundredths) {
    // Split before multiplication to keep valid commercial values in int64.
    return (cents/10000)*hundredths+((cents%10000)*hundredths+5000)/10000;
}
}
