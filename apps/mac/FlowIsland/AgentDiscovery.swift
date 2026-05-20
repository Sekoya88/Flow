import Foundation

private let API_BASE = "http://localhost:18000/api/v1/local"

class AgentDiscovery {
    private var timer: Timer?
    private weak var wsClient: WebSocketClient?
    private weak var store: AppStore?
    private var lastConnectedId: String?

    func start(wsClient: WebSocketClient, store: AppStore) {
        self.wsClient = wsClient
        self.store = store
        poll()
        pollAllAgents()
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            self?.poll()
            self?.pollAllAgents()
        }
    }

    private func poll() {
        guard let url = URL(string: "\(API_BASE)/active-agents") else { return }
        URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
            guard let self, let data else { return }
            guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let agents = json["agents"] as? [[String: Any]],
                  let first = agents.first,
                  let id = first["id"] as? String else { return }
            let name = first["name"] as? String
            if id != self.lastConnectedId {
                self.lastConnectedId = id
                DispatchQueue.main.async {
                    self.wsClient?.connect(agentId: id, name: name)
                }
            }
        }.resume()
    }

    private func pollAllAgents() {
        guard let url = URL(string: "\(API_BASE)/agents") else { return }
        URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
            guard let self, let data else { return }
            guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let agents = json["agents"] as? [[String: Any]] else { return }
            let infos = agents.compactMap { dict -> AgentInfo? in
                guard let id   = dict["id"]   as? String,
                      let name = dict["name"] as? String else { return nil }
                return AgentInfo(id: id, name: name)
            }
            DispatchQueue.main.async {
                self.store?.availableAgents = infos
            }
        }.resume()
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }
}
