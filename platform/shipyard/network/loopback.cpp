#include <winsock2.h>
#include <windows.h>
#include "soh/Network/Network.h"
#include <spdlog/spdlog.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
#include <thread>

class ObservedNetwork : public Network {
  public:
    ObservedNetwork() : Network(Shipyard::SohUI::ValueInit()), connected(0), disconnected(0), rawCalls(0) {}
    Shipyard::Async::mutex observed;
    unsigned connected, disconnected, rawCalls;
    std::vector<nlohmann::json> packets;
    void OnIncomingData(char *) {
        Shipyard::Async::lock_guard<Shipyard::Async::mutex> l(observed);
        ++rawCalls;
    }
    void OnIncomingJson(nlohmann::json packet) {
        Shipyard::Async::lock_guard<Shipyard::Async::mutex> l(observed);
        packets.push_back(packet);
    }
    void OnConnected() {
        {
            Shipyard::Async::lock_guard<Shipyard::Async::mutex> l(observed);
            ++connected;
        }
        nlohmann::json packet;
        packet["client"] = true;
        SendJsonToRemote(packet);
    }
    void OnDisconnected() {
        Shipyard::Async::lock_guard<Shipyard::Async::mutex> l(observed);
        ++disconnected;
    }
    unsigned Count() {
        Shipyard::Async::lock_guard<Shipyard::Async::mutex> l(observed);
        return packets.size();
    }
};
static void WaitPackets(ObservedNetwork &client, unsigned count) {
    DWORD deadline = GetTickCount() + 5000;
    while (client.Count() < count && LONG(deadline - GetTickCount()) > 0)
        Sleep(1);
    assert(client.Count() == count);
}
static SOCKET Accept(SOCKET listener) {
    fd_set readable;
    FD_ZERO(&readable);
    FD_SET(listener, &readable);
    timeval timeout = {5, 0};
    assert(select(0, &readable, NULL, NULL, &timeout) == 1);
    SOCKET peer = accept(listener, NULL, NULL);
    assert(peer != INVALID_SOCKET);
    DWORD milliseconds = 5000;
    setsockopt(peer, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char *>(&milliseconds), sizeof(milliseconds));
    return peer;
}
static std::string Receive(SOCKET peer) {
    std::string result;
    char bytes[113];
    while (result.find('\0') == std::string::npos) {
        int count = recv(peer, bytes, sizeof(bytes), 0);
        assert(count > 0);
        result.append(bytes, count);
    }
    assert(result.back() == '\0');
    result.pop_back();
    return result;
}
static void Send(SOCKET peer, const std::string &data) {
    size_t sent = 0;
    while (sent < data.size()) {
        int n = send(peer, data.data() + sent, int(data.size() - sent), 0);
        assert(n > 0);
        sent += n;
    }
}
int main() {
    spdlog::set_level(spdlog::level::off);
    union Storage {
        double align;
        unsigned char bytes[sizeof(Network)];
    } storage;
    memset(storage.bytes, 0xa5, sizeof(storage.bytes));
    Network *normal = new (storage.bytes) Network;
    assert(!normal->isEnabled && !normal->isConnected);
    normal->~Network();
    Network *initialized = new (storage.bytes) Network(Shipyard::SohUI::ValueInit());
    assert(!initialized->isEnabled && !initialized->isConnected);
    initialized->~Network();
    assert(SDLNet_Init() == 0);
    assert(SDLNet_Init() == 0);
    SDLNet_Quit();
    IPaddress endian;
    assert(SDLNet_ResolveHost(&endian, "127.0.0.1", 258) == 0);
    const unsigned char ip[] = {127, 0, 0, 1}, port[] = {1, 2};
    assert(memcmp(&endian.host, ip, 4) == 0 && memcmp(&endian.port, port, 2) == 0);
    assert(SDLNet_ResolveHost(NULL, "127.0.0.1", 1) == -1 && strlen(SDLNet_GetError()) > 0);
    assert(SDLNet_AllocSocketSet(-1) == NULL);
    SDLNet_SocketSet empty = SDLNet_AllocSocketSet(0);
    assert(empty);
    assert(SDLNet_TCP_AddSocket(empty, NULL) == 0);
    SDLNet_FreeSocketSet(empty);
    SOCKET listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    assert(listener != INVALID_SOCKET);
    sockaddr_in address = {0};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = inet_addr("127.0.0.1");
    assert(bind(listener, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == 0);
    int addressLength = sizeof(address);
    assert(getsockname(listener, reinterpret_cast<sockaddr *>(&address), &addressLength) == 0);
    assert(listen(listener, 2) == 0);
    ObservedNetwork client;
    client.Enable("127.0.0.1", ntohs(address.sin_port));
    SOCKET peer = Accept(listener);
    assert(nlohmann::json::parse(Receive(peer))["client"].get<bool>());
    Send(peer, "{\"id\":1");
    Sleep(10);
    assert(client.Count() == 0);
    std::string data = "}";
    data.push_back('\0');
    data += "{\"id\":2}";
    data.push_back('\0');
    data += "not-json";
    data.push_back('\0');
    data += "{\"id\":3,\"text\":\"\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e\"}";
    data.push_back('\0');
    Send(peer, data);
    WaitPackets(client, 3);
    nlohmann::json large;
    large["id"] = 4;
    large["text"] = std::string(2100, 'x');
    data = large.dump();
    data.push_back('\0');
    for (size_t i = 0; i < data.size(); i += 163)
        Send(peer, data.substr(i, 163));
    WaitPackets(client, 4);
    data = "[]";
    data.push_back('\0');
    data += "null";
    data.push_back('\0');
    data += "true";
    data.push_back('\0');
    data += "{\"id\":5}";
    data.push_back('\0');
    Send(peer, data);
    WaitPackets(client, 8);
    {
        Shipyard::Async::lock_guard<Shipyard::Async::mutex> l(client.observed);
        assert(client.packets[0]["id"] == 1 && client.packets[1]["id"] == 2 && client.packets[2]["id"] == 3);
        assert(client.packets[3]["text"].get<std::string>().size() == 2100);
        assert(client.packets[4].is_array() && client.packets[5].is_null() && client.packets[6].get<bool>());
    }
    std::string outgoing(512 * 1024, 'z');
    std::thread sender([&]() { client.SendDataToRemote(outgoing.c_str()); });
    assert(Receive(peer) == outgoing);
    sender.join();
    Send(peer, "{\"unfinished\":");
    closesocket(peer);
    peer = Accept(listener);
    assert(nlohmann::json::parse(Receive(peer))["client"].get<bool>());
    data = "{\"id\":9}";
    data.push_back('\0');
    Send(peer, data);
    WaitPackets(client, 9);
    assert(client.packets.back()["id"] == 9);
    client.Disable();
    assert(!client.isEnabled && !client.isConnected);
    closesocket(peer);
    closesocket(listener);
    assert(client.connected == 2 && client.disconnected == 2 && client.rawCalls > 0);
    SDLNet_Quit();
    SOCKET after = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    assert(after == INVALID_SOCKET && WSAGetLastError() == WSANOTINITIALISED);
    puts("real Network loopback: 9 framed JSON packets; split/coalesced/malformed/UTF8/2100-byte input; 524288-byte "
         "send; reconnect reset; joined shutdown; lifecycle and byte order passed");
}
