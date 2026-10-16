import Foundation
import Security
import Darwin

// Fixed service/account: no caller-supplied destination or credential selection.
let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                         kSecAttrService as String: "local.waveshare.deepseek",
                         kSecAttrAccount as String: "balance-monitor"]
func fail(_ code: Int32) -> Never { exit(code) }
let mode = CommandLine.arguments.dropFirst().first ?? ""
if mode == "set" {
    guard isatty(STDIN_FILENO) != 0 else { fail(2) }
    print("API Key 仅保存到本机钥匙串，用于 api.deepseek.com 的 HTTPS 余额查询。")
    guard let raw = getpass("请输入 DeepSeek API Key（输入不可见）: ") else { fail(2) }
    let key = String(cString: raw).trimmingCharacters(in: .whitespacesAndNewlines)
    memset(raw, 0, strlen(raw))
    guard key.hasPrefix("sk-"), key.count >= 12, key.count <= 512,
          key.utf8.allSatisfy({ $0 >= 33 && $0 <= 126 }) else {
        print("Key 格式无效，未保存。"); fail(2)
    }
    let attributes: [String: Any] = [kSecValueData as String: Data(key.utf8)]
    var status = SecItemUpdate(base as CFDictionary, attributes as CFDictionary)
    if status == errSecItemNotFound {
        var item = base
        item[kSecValueData as String] = Data(key.utf8)
        item[kSecAttrLabel as String] = "Waveshare DeepSeek balance monitor"
        status = SecItemAdd(item as CFDictionary, nil)
    }
    guard status == errSecSuccess else { print("钥匙串保存失败，错误码 \(status)。"); fail(3) }
    print("已保存。后台会在下一次轮询时读取余额（约一分钟）。")
} else if mode == "read" {
    // Background polling must never leave an interactive Keychain prompt open.
    SecKeychainSetUserInteractionAllowed(false)
    var query = base
    query[kSecReturnData as String] = true
    query[kSecMatchLimit as String] = kSecMatchLimitOne
    var result: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &result)
    guard status == errSecSuccess, let data = result as? Data else { fail(status == errSecItemNotFound ? 4 : 5) }
    // Parent captures this pipe; never run this mode interactively.
    guard isatty(STDOUT_FILENO) == 0 else { fail(6) }
    FileHandle.standardOutput.write(data)
} else { fail(2) }
