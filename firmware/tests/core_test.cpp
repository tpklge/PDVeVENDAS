#include "../core/money.hpp"
#include "../core/hid.hpp"
#include "../core/installation.hpp"
#include <cassert>
#include <limits>

int main() {
    using namespace tab5;
    assert(hid_character(0x04, 0) == 'a');
    assert(hid_character(0x04, 2) == 'A');
    assert(hid_character(0x1e, 0) == '1');
    assert(hid_character(0x1e, 2) == '!');
    assert(hid_character(0x31, 0) == '\\');
    assert(hid_character(0x34, 0) == '\'');
    assert(hid_character(0x52, 0) == 0);
    assert(hid_character(0xff, 0) == 0);
    assert(line_total(1999, 1500).value() == 2999);
    assert(line_total(1999, 1500, 99).value() == 2900);
    assert(!line_total(1, 0));
    assert(!line_total(-1, 1000));
    assert(!line_total(100, 1000, 101));
    assert(!line_total(std::numeric_limits<std::int64_t>::max(), 1001));
    assert(line_total(0, 1000).value() == 0);
    Installation install(false);
    Evidence e;
    assert(!install.advance(e));
    e.hardware_ok = e.touch_ok = e.virtual_keyboard_available = true;
    assert(install.advance(e)); // No SD: setup still proceeds.
    e.wifi_connected = e.address_valid = true;
    assert(install.advance(e));
    e.time_valid = e.dns_valid = e.tls_chain_valid = e.health_ready = e.api_compatible = true;
    assert(!install.advance(e)); // A valid chain alone cannot bypass hostname verification.
    e.hostname_valid = true;
    assert(install.advance(e));
    e.schema_valid = e.installation_identified = true;
    assert(install.advance(e));
    e.remote_admin_authenticated = e.remote_admin_authorized = e.initial_password_changed = true;
    assert(!install.advance(e));
    e.local_verifier_protected = true;
    assert(install.advance(e));
    assert(!install.advance(e)); // Do not mark first boot complete before durable storage.
    e.config_persisted = true;
    assert(install.advance(e));
    assert(install.stage() == InstallationStage::Complete);
    assert(!install.advance(e));
    assert(!Installation::commercial_access(false, true));
    assert(!Installation::commercial_access(true, false));
    assert(Installation::commercial_access(true, true));
    assert(!Installation::persistent_queue_available(false, true, true));
    assert(!Installation::persistent_queue_available(true, true, false));
    assert(Installation(true).stage() == InstallationStage::Complete);
}
