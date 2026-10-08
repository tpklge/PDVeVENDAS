#pragma once
#include <cerrno>
#include <cstdio>
#include <string>
#include <unistd.h>

namespace tab5 {
enum class FileRead { Found, Missing, Error };
inline FileRead read_settings_file(const std::string& path, void* data, size_t size) {
    FILE* file = fopen(path.c_str(), "rb");
    if (!file) return errno == ENOENT ? FileRead::Missing : FileRead::Error;
    bool ok = fread(data, 1, size, file) == size;
    ok = fgetc(file) == EOF && !ferror(file) && ok;
    ok = fclose(file) == 0 && ok;
    return ok ? FileRead::Found : FileRead::Error;
}
inline FileRead load_settings_file(const std::string& path, void* data, size_t size) {
    const auto result = read_settings_file(path, data, size);
    return result == FileRead::Missing ? read_settings_file(path + ".bak", data, size) : result;
}
inline bool remove_settings_path(const std::string& path) {
    return unlink(path.c_str()) == 0 || errno == ENOENT;
}
inline bool commit_settings_temp(const std::string& path) {
    const std::string temp = path + ".tmp", backup = path + ".bak";
    if (access(path.c_str(), F_OK) == 0) {
        if (!remove_settings_path(backup) || rename(path.c_str(), backup.c_str()) != 0) return false;
    } else if (errno != ENOENT) return false;
    if (rename(temp.c_str(), path.c_str()) != 0) {
        rename(backup.c_str(), path.c_str());
        return false;
    }
    return true;
}
inline bool save_settings_file(const std::string& path, const void* data, size_t size) {
    const std::string temp = path + ".tmp", backup = path + ".bak";
    FILE* file = fopen(temp.c_str(), "wb");
    if (!file) return false;
    bool ok = fwrite(data, 1, size, file) == size;
    ok = fflush(file) == 0 && ok;
    ok = fsync(fileno(file)) == 0 && ok;
    ok = fclose(file) == 0 && ok;
    if (!ok) { remove_settings_path(temp); return false; }
    // FAT rename cannot replace an existing file. Keep the committed copy
    // until the complete temporary file is flushed; recover .bak at boot.
    if (commit_settings_temp(path)) return true;
    remove_settings_path(temp); return false;
}
inline bool erase_settings_files(const std::string& path) {
    // Remove fallback first so an interrupted reset cannot resurrect it.
    return remove_settings_path(path + ".tmp") && remove_settings_path(path + ".bak") && remove_settings_path(path);
}
}
