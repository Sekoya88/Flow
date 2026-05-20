import Foundation
import SwiftUI

// MARK: - AgentState

enum AgentState: Equatable {
    case idle, thinking, reflecting

    var label: String {
        switch self {
        case .idle:       return "Idle"
        case .thinking:   return "Thinking…"
        case .reflecting: return "Reflecting…"
        }
    }

    var emoji: String {
        switch self {
        case .idle:       return ""
        case .thinking:   return "⚡"
        case .reflecting: return "✦"
        }
    }

    var color: Color {
        switch self {
        case .idle:       return Color(nsColor: .systemGray)
        case .thinking:   return Color(red: 0.23, green: 0.51, blue: 0.96)
        case .reflecting: return Color(red: 0.65, green: 0.55, blue: 0.98)
        }
    }
}

// MARK: - AgentEvent

struct AgentEvent: Identifiable {
    let id        = UUID()
    let type      : String
    let timestamp : Date
    let payload   : [String: Any]

    var description: String {
        switch type {
        case "skills_matched":
            let skills = (payload["skills"] as? [[String: Any]])?.compactMap { $0["name"] as? String } ?? []
            return "Skills: \(skills.joined(separator: ", ").isEmpty ? "—" : skills.joined(separator: ", "))"
        case "metacog_evaluated":
            let grade     = payload["grade"] as? Int ?? 0
            let mutations = payload["mutations_proposed"] as? Int ?? 0
            let bar = String(repeating: "█", count: grade) + String(repeating: "░", count: max(0, 5 - grade))
            return "Reflection \(bar) \(grade)/5  +\(mutations) mutations"
        case "skill_arm_updated":
            let reward = (payload["reward"] as? Double ?? 0)
            let id     = (payload["skill_id"] as? String ?? "").prefix(8)
            return String(format: "Bandit reward %.2f → %@…", reward, id)
        case "connection_established":
            return "Connected to Flow"
        default:
            return type
        }
    }
}

// MARK: - WebSocketClient

class WebSocketClient: ObservableObject {
    @Published var isConnected   : Bool        = false
    @Published var events        : [AgentEvent] = []
    @Published var skills        : [SkillNode]  = []
    @Published var agentState    : AgentState   = .idle
    @Published var reconnectAttempt: Int        = 0

    private(set) var currentAgentId: String?

    private var webSocketTask   : URLSessionWebSocketTask?
    private let urlSession       = URLSession(configuration: .default)
    private var reconnectDelay   : TimeInterval = 1.0
    private var stateResetTimer  : Timer?

    // MARK: - Connect / Disconnect

    func connect(agentId: String) {
        guard agentId != currentAgentId || !isConnected else { return }
        disconnect()
        currentAgentId = agentId
        reconnectDelay = 1.0
        reconnectAttempt = 0
        openConnection(agentId: agentId)
    }

    func disconnect() {
        currentAgentId = nil
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        DispatchQueue.main.async {
            self.isConnected = false
            self.reconnectAttempt = 0
        }
    }

    // MARK: - Internal connection

    private func openConnection(agentId: String) {
        guard let url = URL(string: "ws://localhost:18000/api/v1/agents/\(agentId)/ws-observability") else { return }
        webSocketTask = urlSession.webSocketTask(with: url)
        webSocketTask?.resume()
        DispatchQueue.main.async { self.isConnected = true }
        receiveMessage()
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure:
                DispatchQueue.main.async { self.isConnected = false }
                self.scheduleReconnect()

            case .success(let message):
                if case .string(let text) = message,
                   let data = text.data(using: .utf8),
                   let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let type = dict["type"] as? String {
                    DispatchQueue.main.async {
                        self.handleEvent(type: type, payload: dict)
                    }
                }
                self.receiveMessage()
            }
        }
    }

    // MARK: - Event handling

    private func handleEvent(type: String, payload: [String: Any]) {
        let event = AgentEvent(type: type, timestamp: Date(), payload: payload)
        events.insert(event, at: 0)
        if events.count > 60 { events.removeLast() }

        switch type {
        case "skills_matched":
            let incoming = (payload["skills"] as? [[String: Any]])?.compactMap { $0["name"] as? String } ?? []
            updateSkills(activeNames: Set(incoming))
            agentState = .thinking

        case "metacog_evaluated":
            agentState = .reflecting
            stateResetTimer?.invalidate()
            stateResetTimer = Timer.scheduledTimer(withTimeInterval: 3, repeats: false) { [weak self] _ in
                DispatchQueue.main.async { self?.agentState = .idle }
            }

        case "skill_arm_updated":
            let skillId = payload["skill_id"] as? String ?? ""
            let reward  = payload["reward"]   as? Double  ?? 0
            if let i = skills.firstIndex(where: { $0.id == skillId }) {
                skills[i].score = reward
            }

        default:
            break
        }
    }

    private func updateSkills(activeNames: Set<String>) {
        var map = Dictionary(uniqueKeysWithValues: skills.map { ($0.name, $0) })
        activeNames.forEach { name in
            if map[name] == nil {
                map[name] = SkillNode(id: name, name: name, score: 0.5, active: true)
            } else {
                map[name]!.active = true
            }
        }
        map.keys.forEach { key in
            if !activeNames.contains(key) { map[key]!.active = false }
        }
        skills = Array(map.values)
    }

    // MARK: - Reconnect

    private func scheduleReconnect() {
        guard let agentId = currentAgentId else { return }
        let delay = reconnectDelay
        reconnectDelay = min(reconnectDelay * 2, 30.0)
        DispatchQueue.main.async { self.reconnectAttempt += 1 }
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            guard let self, self.currentAgentId == agentId else { return }
            self.openConnection(agentId: agentId)
        }
    }
}
