import SwiftUI
import AppKit

private let WEB_APP          = "http://localhost:13000"
private let API_BASE         = "http://localhost:18000/api/v1/local"
private let PILL_W:  CGFloat = 200
private let PILL_H:  CGFloat = 37
private let PANEL_W: CGFloat = 540
private let PANEL_H: CGFloat = 500

// ContentView fills the NSPanel (always full-size, transparent).
// The morphing notchContent sits at the top and is the only visible element.
struct ContentView: View {
    @ObservedObject var store: AppStore

    var body: some View {
        ZStack(alignment: .top) {
            Color.clear
            NotchMorphView(store: store)
        }
    }
}

// MARK: - Dynamic Island morph

struct NotchMorphView: View {
    @ObservedObject var store: AppStore

    private var isOpen:     Bool { store.notchState     == .open }
    private var isHovering: Bool { store.isHoveringPill && !isOpen }

    var body: some View {
        VStack(spacing: 0) {
            pillRow
                .frame(height: PILL_H)

            panelBody
                .frame(height: PANEL_H - PILL_H)
                .opacity(isOpen ? 1 : 0)
                .animation(
                    isOpen
                        ? .easeIn(duration: 0.12).delay(0.08)
                        : .easeOut(duration: 0.08),
                    value: isOpen
                )
        }
        .frame(
            width:  isOpen ? PANEL_W : PILL_W,
            height: isOpen ? PANEL_H  : PILL_H,
            alignment: .top
        )
        .background(Color.black)
        .clipShape(
            NotchShape(
                topRadius:    isOpen ? 20 : 8,
                bottomRadius: isOpen ? 24 : 20
            )
        )
        // Hover glow — soft white halo before expansion
        .shadow(
            color: isHovering ? .white.opacity(0.18) : (isOpen ? .black.opacity(0.55) : .clear),
            radius: isHovering ? 12 : 22,
            y: isHovering ? 0 : 12
        )
        // Hover scale — pill slightly grows before opening
        .scaleEffect(isHovering ? 1.05 : 1.0)
        .animation(
            isHovering
                ? .spring(response: 0.18, dampingFraction: 0.65)
                : .spring(response: 0.45, dampingFraction: 1.0),
            value: isHovering
        )
        .animation(
            isOpen
                ? .spring(response: 0.42, dampingFraction: 0.8)
                : .spring(response: 0.45, dampingFraction: 1.0),
            value: store.notchState
        )
    }

    // MARK: - Pill row

    private var pillRow: some View {
        HStack(spacing: 7) {
            Circle()
                .fill(store.wsClient.isConnected ? Color.green : Color(nsColor: .systemGray))
                .frame(width: 7, height: 7)
                .shadow(color: store.wsClient.isConnected ? .green.opacity(0.8) : .clear, radius: 4)
                // Dot pulses brighter on hover
                .brightness(isHovering ? 0.3 : 0)

            Text("Flow")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(.white)
                .tracking(-0.5)

            if store.wsClient.agentState != .idle {
                Text(store.wsClient.agentState.emoji)
                    .font(.system(size: 11))
                    .foregroundColor(store.wsClient.agentState.color)
            }
        }
        .padding(.horizontal, 16)
        .frame(maxWidth: .infinity)
    }

    // MARK: - Expanded panel

    private var panelBody: some View {
        VStack(spacing: 0) {
            headerRow
            if !store.wsClient.isConnected { noAgentBanner }

            // Tab content
            switch store.activeTab {
            case .overview: overviewContent
            case .runs:     RunsTabView(agentId: store.wsClient.currentAgentId)
            case .memory:   MemoryTabView(agentId: store.wsClient.currentAgentId)
            }

            footerRow
        }
    }

    // MARK: Header

    private var headerRow: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(store.wsClient.isConnected
                      ? Color.green
                      : Color(nsColor: .systemGray).opacity(0.4))
                .frame(width: 7, height: 7)
                .shadow(color: store.wsClient.isConnected ? .green.opacity(0.7) : .clear, radius: 4)

            Text("Flow")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(.white)

            if let id = store.wsClient.currentAgentId {
                Text(store.wsClient.agentName ?? (String(id.prefix(8)) + "…"))
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(Color(nsColor: .systemGray))
            }

            Spacer()

            stateBadge
            openButton
            quitButton
        }
        .padding(.horizontal, 16)
        .padding(.top, 12)
        .padding(.bottom, 10)
        .overlay(Divider().opacity(0.1), alignment: .bottom)
    }

    private var stateBadge: some View {
        Text(store.wsClient.agentState.label)
            .font(.system(size: 10, weight: .semibold))
            .foregroundColor(store.wsClient.agentState.color)
            .padding(.horizontal, 8)
            .padding(.vertical, 2)
            .background(store.wsClient.agentState.color.opacity(0.08))
            .overlay(Capsule().stroke(store.wsClient.agentState.color.opacity(0.2), lineWidth: 1))
            .clipShape(Capsule())
    }

    private var openButton: some View {
        Button("↗ Open") {
            // Go straight to dashboard — skip public landing page
            NSWorkspace.shared.open(URL(string: "\(WEB_APP)/dashboard")!)
        }
        .buttonStyle(GlassButtonStyle(accent: true))
    }

    private var quitButton: some View {
        Button("✕") { NSApplication.shared.terminate(nil) }
            .buttonStyle(GlassButtonStyle(accent: false))
            .help("Quit Flow")
    }

    // MARK: No-agent banner

    private var noAgentBanner: some View {
        Text("No agent connected — start a Flow agent to see live data")
            .font(.system(size: 11))
            .foregroundColor(Color(nsColor: .systemGray))
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.red.opacity(0.06))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.red.opacity(0.15), lineWidth: 1))
            .padding(.horizontal, 16)
            .padding(.top, 8)
    }

    // MARK: Overview tab (skill graph + events)

    private var overviewContent: some View {
        VStack(spacing: 0) {
            skillGraphSection
            Divider().opacity(0.15).padding(.horizontal, 16)
            eventFeedSection
        }
    }

    private var skillGraphSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            sectionLabel("Skill graph")
            SkillGraphView(skills: store.wsClient.skills)
                .frame(height: 130)
        }
        .padding(.horizontal, 16)
        .padding(.top, 10)
        .padding(.bottom, 4)
    }

    private var eventFeedSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            sectionLabel("Live events")
            EventFeedView(events: store.wsClient.events)
                .frame(height: 150)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 10)
    }

    // MARK: Footer — tab switcher

    private var footerRow: some View {
        HStack(spacing: 5) {
            tabBtn("This Agent", tab: .overview)
            tabBtn("Runs",       tab: .runs)
            tabBtn("Memory",     tab: .memory)
        }
        .padding(.horizontal, 16)
        .padding(.top, 6)
        .padding(.bottom, 14)
        .overlay(Divider().opacity(0.08), alignment: .top)
    }

    private func tabBtn(_ label: String, tab: PanelTab) -> some View {
        Button(label) { store.activeTab = tab }
            .buttonStyle(TabButtonStyle(active: store.activeTab == tab))
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 9, weight: .bold))
            .foregroundColor(Color(nsColor: .systemGray).opacity(0.7))
            .tracking(1.2)
    }
}

// MARK: - Runs tab

struct RunsTabView: View {
    let agentId: String?

    struct RunRow: Identifiable {
        let id, status, message, createdAt: String
    }

    @State private var runs: [RunRow] = []
    @State private var loading = true

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                sectionLabel("Recent runs")
                Spacer()
                if loading { ProgressView().scaleEffect(0.5) }
            }
            if runs.isEmpty && !loading {
                emptyState("No runs yet")
            } else {
                VStack(spacing: 4) {
                    ForEach(runs) { run in
                        RunRowView(run: run)
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .padding(.top, 10)
        .padding(.bottom, 4)
        .frame(maxHeight: .infinity)
        .onAppear { fetchRuns() }
        .onChange(of: agentId) { _ in fetchRuns() }
    }

    private func fetchRuns() {
        guard let id = agentId else { loading = false; return }
        guard let url = URL(string: "\(API_BASE)/agent-executions/\(id)") else { return }
        loading = true
        URLSession.shared.dataTask(with: url) { data, _, _ in
            let rows = (try? JSONSerialization.jsonObject(with: data ?? Data()) as? [String: Any])
                .flatMap { $0["executions"] as? [[String: Any]] } ?? []
            DispatchQueue.main.async {
                runs = rows.map {
                    RunRow(
                        id:        $0["id"]         as? String ?? "",
                        status:    $0["status"]      as? String ?? "unknown",
                        message:   $0["message"]     as? String ?? "",
                        createdAt: $0["created_at"]  as? String ?? ""
                    )
                }
                loading = false
            }
        }.resume()
    }
}

struct RunRowView: View {
    let run: RunsTabView.RunRow

    private var dotColor: Color {
        switch run.status {
        case "completed": return .green
        case "running":   return Color(red: 0.23, green: 0.51, blue: 0.96)
        default:          return Color(nsColor: .systemGray)
        }
    }

    var body: some View {
        HStack(spacing: 8) {
            Circle().fill(dotColor).frame(width: 6, height: 6)
            Text(run.message.isEmpty ? "(no message)" : run.message)
                .font(.system(size: 10))
                .foregroundColor(.white.opacity(0.85))
                .lineLimit(1)
            Spacer()
            Text(run.status)
                .font(.system(size: 9, weight: .semibold))
                .foregroundColor(dotColor)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 5)
        .background(Color.white.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

// MARK: - Memory tab

struct MemoryTabView: View {
    let agentId: String?

    struct MemRow: Identifiable {
        let id, content, createdAt: String
    }

    @State private var memories: [MemRow] = []
    @State private var loading = true

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                sectionLabel("Memory")
                Spacer()
                if loading { ProgressView().scaleEffect(0.5) }
            }
            if memories.isEmpty && !loading {
                emptyState("No memory entries yet")
            } else {
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: 4) {
                        ForEach(memories) { mem in
                            MemRowView(mem: mem)
                        }
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .padding(.top, 10)
        .padding(.bottom, 4)
        .frame(maxHeight: .infinity)
        .onAppear { fetchMemory() }
        .onChange(of: agentId) { _ in fetchMemory() }
    }

    private func fetchMemory() {
        guard let id = agentId else { loading = false; return }
        guard let url = URL(string: "\(API_BASE)/agent-memory/\(id)") else { return }
        loading = true
        URLSession.shared.dataTask(with: url) { data, _, _ in
            let rows = (try? JSONSerialization.jsonObject(with: data ?? Data()) as? [String: Any])
                .flatMap { $0["memories"] as? [[String: Any]] } ?? []
            DispatchQueue.main.async {
                memories = rows.map {
                    MemRow(
                        id:        $0["id"]         as? String ?? "",
                        content:   $0["content"]    as? String ?? "",
                        createdAt: $0["created_at"] as? String ?? ""
                    )
                }
                loading = false
            }
        }.resume()
    }
}

struct MemRowView: View {
    let mem: MemoryTabView.MemRow

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "brain")
                .font(.system(size: 9))
                .foregroundColor(Color(red: 0.65, green: 0.55, blue: 0.98))
                .padding(.top, 2)
            Text(mem.content)
                .font(.system(size: 10))
                .foregroundColor(.white.opacity(0.8))
                .lineLimit(2)
            Spacer()
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 5)
        .background(Color.white.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

// MARK: - Shared helpers

private func sectionLabel(_ text: String) -> some View {
    Text(text.uppercased())
        .font(.system(size: 9, weight: .bold))
        .foregroundColor(Color(nsColor: .systemGray).opacity(0.7))
        .tracking(1.2)
}

private func emptyState(_ text: String) -> some View {
    Text(text)
        .font(.system(size: 11))
        .foregroundColor(Color(nsColor: .systemGray).opacity(0.6))
        .frame(maxWidth: .infinity)
        .padding(.top, 24)
}

// MARK: - Button styles

struct GlassButtonStyle: ButtonStyle {
    let accent: Bool
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 11, weight: .semibold))
            .foregroundColor(accent
                             ? Color(red: 0.65, green: 0.71, blue: 0.99)
                             : Color(nsColor: .systemGray))
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(RoundedRectangle(cornerRadius: 8)
                .fill(accent
                      ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(configuration.isPressed ? 0.35 : 0.18)
                      : Color.white.opacity(configuration.isPressed ? 0.1 : 0.05)))
            .overlay(RoundedRectangle(cornerRadius: 8)
                .stroke(accent
                        ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(0.4)
                        : Color.white.opacity(0.1), lineWidth: 1))
    }
}

struct TabButtonStyle: ButtonStyle {
    let active: Bool
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 10, weight: active ? .bold : .semibold))
            .foregroundColor(active
                             ? Color(red: 0.65, green: 0.71, blue: 0.99)
                             : Color(nsColor: .systemGray))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
            .background(RoundedRectangle(cornerRadius: 8)
                .fill(active
                      ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(0.15)
                      : Color.white.opacity(configuration.isPressed ? 0.08 : 0.04)))
            .overlay(RoundedRectangle(cornerRadius: 8)
                .stroke(active
                        ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(0.35)
                        : Color.white.opacity(0.07), lineWidth: 1))
    }
}
