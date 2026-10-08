#include "../core/module_policy.hpp"
#include <cassert>
int main(){
    assert(tab5::has_module_permission("products.read sales.read","products.read"));
    assert(tab5::has_module_permission("products.read sales.read","sales.read"));
    assert(!tab5::has_module_permission("products.readonly","products.read"));
    assert(!tab5::has_module_permission("sales.read","products.read"));
    assert(!tab5::has_module_permission("","products.read"));
    assert(tab5::has_module_permission("",nullptr));
}
