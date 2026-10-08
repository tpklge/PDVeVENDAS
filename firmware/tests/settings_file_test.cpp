#include "../core/settings_file.hpp"
#include <cassert>
#include <cstdlib>
#include <cstring>

int main() {
    char directory[] = "/tmp/tab5-settings-XXXXXX";
    assert(mkdtemp(directory));
    const std::string path = std::string(directory) + "/settings.enc";
    unsigned char first[64], second[64], loaded[64]{};
    memset(first, 0x11, sizeof(first)); memset(second, 0x22, sizeof(second));
    assert(tab5::load_settings_file(path, loaded, sizeof(loaded)) == tab5::FileRead::Missing);
    assert(tab5::save_settings_file(path, first, sizeof(first)));
    assert(tab5::save_settings_file(path, second, sizeof(second)));
    assert(tab5::load_settings_file(path, loaded, sizeof(loaded)) == tab5::FileRead::Found);
    assert(memcmp(loaded, second, sizeof(second)) == 0);
    // A reset between the two renames recovers the last complete copy.
    assert(unlink(path.c_str()) == 0);
    assert(tab5::load_settings_file(path, loaded, sizeof(loaded)) == tab5::FileRead::Found);
    assert(memcmp(loaded, first, sizeof(first)) == 0);
    assert(!tab5::save_settings_file(path + "/missing/settings.enc", second, sizeof(second)));
    assert(tab5::save_settings_file(path, second, sizeof(second)));
    FILE* file = fopen(path.c_str(), "wb"); assert(file);
    assert(fwrite(first, 1, 3, file) == 3); assert(fclose(file) == 0);
    assert(tab5::load_settings_file(path, loaded, sizeof(loaded)) == tab5::FileRead::Error);
    assert(tab5::erase_settings_files(path));
    assert(tab5::load_settings_file(path, loaded, sizeof(loaded)) == tab5::FileRead::Missing);
    assert(rmdir(directory) == 0);
    puts("PASS: settings persist, interrupted save recovery, I/O failure, corruption, reset.");
}
