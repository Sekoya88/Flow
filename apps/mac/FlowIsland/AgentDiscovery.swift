import Foundation

private let API_BASE = "http://localhost:18000/api/v1/local"

class AgentDiscovery {
    private var timer: Timer?
    private weak var wsClient: WebSocketClient?
    private var lastConnectedId: String?

    func start(wsClient: WebSocketClient) {
        self.wsClient = wsClient
        poll()
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            self?.poll()
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

    func stop() {
        timer?.invalidate()
        timer = nil
    }
}
