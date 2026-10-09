#include "../core/finance_input.hpp"
#include <cassert>
#include <initializer_list>
int main(){
    using tab5::valid_financial_date;
    assert(valid_financial_date("2026-10-09"));
    assert(valid_financial_date("2024-02-29"));
    assert(valid_financial_date("2000-02-29"));
    assert(valid_financial_date("1000-01-01"));
    assert(valid_financial_date("9999-12-31"));
    for(auto* invalid:{"2026-02-29","2100-02-29","2026-04-31","2026-00-01","2026-13-01","2026-10-00","2026-10-32","0999-12-31","2026-1-01","2026/10/09","2026-10-09x","abcd-ef-gh",""})assert(!valid_financial_date(invalid));
    assert(!valid_financial_date(nullptr));
}
