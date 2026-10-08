#pragma once
#include <cstdint>

namespace tab5 {
enum class InstallationStage : std::uint8_t {
    Preparation, Wifi, Server, Database, Administrator, Finish, Complete
};
struct Evidence {
    bool hardware_ok = false;
    bool touch_ok = false;
    bool keyboard_ok = false;
    bool virtual_keyboard_available = false;
    bool sd_available = false;
    bool wifi_connected = false;
    bool address_valid = false;
    bool time_valid = false;
    bool dns_valid = false;
    bool tls_chain_valid = false;
    bool hostname_valid = false;
    bool health_ready = false;
    bool api_compatible = false;
    bool schema_valid = false;
    bool installation_identified = false;
    bool remote_admin_authenticated = false;
    bool remote_admin_authorized = false;
    bool initial_password_changed = false;
    bool local_verifier_protected = false;
    bool config_persisted = false;
};

class Installation {
public:
    explicit Installation(bool configured) : stage_(configured ? InstallationStage::Complete : InstallationStage::Preparation) {}
    InstallationStage stage() const { return stage_; }
    bool advance(const Evidence& e) {
        bool valid = false;
        switch (stage_) {
        case InstallationStage::Preparation:
            valid = e.hardware_ok && e.touch_ok && (e.keyboard_ok || e.virtual_keyboard_available); break;
        case InstallationStage::Wifi:
            valid = e.wifi_connected && e.address_valid; break;
        case InstallationStage::Server:
            valid = e.time_valid && e.dns_valid && e.tls_chain_valid && e.hostname_valid && e.health_ready && e.api_compatible; break;
        case InstallationStage::Database:
            valid = e.schema_valid && e.installation_identified; break;
        case InstallationStage::Administrator:
            valid = e.remote_admin_authenticated && e.remote_admin_authorized && e.initial_password_changed && e.local_verifier_protected; break;
        case InstallationStage::Finish:
            valid = e.config_persisted && e.wifi_connected && e.health_ready; break;
        case InstallationStage::Complete:
            return false;
        }
        if (valid) stage_ = static_cast<InstallationStage>(static_cast<unsigned>(stage_) + 1);
        return valid;
    }
    // Local recovery authorization cannot substitute for a remote ERP session.
    static bool commercial_access(bool remote_session_valid, bool permission_granted) {
        return remote_session_valid && permission_granted;
    }
    static bool persistent_queue_available(bool sd_mounted, bool writable, bool integrity_valid) {
        return sd_mounted && writable && integrity_valid;
    }
private:
    InstallationStage stage_;
};
}
