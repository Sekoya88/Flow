import SwiftUI
import AppKit

private let WEB_APP = "http://localhost:13000"

struct ContentView: View {
    @ObservedObject var store: AppStore

    var body: some View {
        ZStack(alignment: .top) {
            // Transparent notch area (pill lives here)
            Color.clear

            // Pill — always visible, no background
            PillView(connected: store.wsClient.isConnected, agentState: store.wsClient.agentState)

            // Panel — slides in below notch when expanded
            if store.isExpanded {
                VStack(spacing: 0) {
                    // Push panel below notch area
                    Spacer()
                    PanelView(store: store)
                }
            }
        }
    }
}

// MARK: - Pill

struct PillView: View {
    let connected: Bool
    let agentState: AgentState

    var body: some View {
        HStack(spacing: 7) {
            Circle()
                .fill(connected ? Color.green : Color(nsColor: .systemGray))
                .frame(width: 7, height: 7)
                .shadow(color: connected ? .green.opacity(0.8) : .clear, radius: 4)

            Text("Flow")
                .font(.system(size: 13, weight: .bold, design: .default))
                .foregroundColor(.white)
                .tracking(-0.5)

            if agentState != .idle {
                Text(agentState.emoji)
                    .font(.system(size: 11))
                    .foregroundColor(agentState.color)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.black.opacity(0.01)) // forces compositing layer
    }
}

// MARK: - Panel

struct PanelView: View {
    @ObservedObject var store: AppStore

    var body: some View {
        ZStack {
            // Native dark glass via NSVisualEffectView
            VisualEffectBackground()
                .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))

            VStack(spacing: 0) {
                headerRow
                if !store.wsClient.isConnected {
                    noAgentBanner
                }
                skillGraphSection
                Divider().opacity(0.15).padding(.horizontal, 16)
                eventFeedSection
                footerRow
            }
        }
        .frame(width: 420, height: 560)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(Color.white.opacity(0.09), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.8), radius: 32, y: 16)
        .transition(.move(edge: .top).combined(with: .opacity))
        .animation(.spring(response: 0.28, dampingFraction: 0.82), value: store.isExpanded)
    }

    // MARK: Header

    private var headerRow: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(store.wsClient.isConnected ? Color.green : Color(nsColor: .systemGray).opacity(0.4))
                .frame(width: 7, height: 7)
                .shadow(color: store.wsClient.isConnected ? .green.opacity(0.7) : .clear, radius: 4)

            Text("Flow")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(.white)

            if let id = store.wsClient.currentAgentId {
                Text(String(id.prefix(8)) + "…")
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(Color(nsColor: .systemGray))
            }

            Spacer()

            stateBadge

            openButton

            quitButton
        }
        .padding(.horizontal, 16)
        .padding(.top, 14)
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
            .overlay(
                Capsule().stroke(store.wsClient.agentState.color.opacity(0.2), lineWidth: 1)
            )
            .clipShape(Capsule())
    }

    private var openButton: some View {
        Button("↗ Open") {
            NSWorkspace.shared.open(URL(string: WEB_APP)!)
        }
        .buttonStyle(GlassButtonStyle(accent: true))
    }

    private var quitButton: some View {
        Button("✕") {
            NSApplication.shared.terminate(nil)
        }
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

    // MARK: Skill graph

    private var skillGraphSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            sectionLabel("Skill graph")
            SkillGraphView(skills: store.wsClient.skills)
                .frame(height: 140)
        }
        .padding(.horizontal, 16)
        .padding(.top, 10)
        .padding(.bottom, 4)
    }

    // MARK: Event feed

    private var eventFeedSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            sectionLabel("Live events")
            EventFeedView(events: store.wsClient.events)
                .frame(height: 160)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 10)
    }

    // MARK: Footer

    private var footerRow: some View {
        HStack(spacing: 5) {
            footerButton(
                label: "This Agent",
                path: store.wsClient.currentAgentId.map { "/agents/\($0)" } ?? "/agents",
                title: "Open current agent details"
            )
            footerButton(
                label: "Runs",
                path: store.wsClient.currentAgentId.map { "/agents/\($0)/executions" } ?? "/executions",
                title: "View recent runs"
            )
            footerButton(
                label: "Memory",
                path: store.wsClient.currentAgentId.map { "/agents/\($0)/memory" } ?? "/memory",
                title: "View agent memory"
            )
        }
        .padding(.horizontal, 16)
        .padding(.top, 6)
        .padding(.bottom, 14)
        .overlay(Divider().opacity(0.08), alignment: .top)
    }

    private func footerButton(label: String, path: String, title: String) -> some View {
        Button(label) {
            NSWorkspace.shared.open(URL(string: WEB_APP + path)!)
        }
        .buttonStyle(FooterButtonStyle())
        .help(title)
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 9, weight: .bold))
            .foregroundColor(Color(nsColor: .systemGray).opacity(0.7))
            .tracking(1.2)
    }
}

// MARK: - NSVisualEffectView wrapper (dark glass)

struct VisualEffectBackground: NSViewRepresentable {
    func makeNSView(context: Context) -> NSVisualEffectView {
        let v = NSVisualEffectView()
        v.material = .hudWindow
        v.blendingMode = .behindWindow
        v.state = .active
        v.appearance = NSAppearance(named: .darkAqua)
        return v
    }
    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {}
}

// MARK: - Button styles

struct GlassButtonStyle: ButtonStyle {
    let accent: Bool
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 11, weight: .semibold))
            .foregroundColor(accent ? Color(red: 0.65, green: 0.71, blue: 0.99) : Color(nsColor: .systemGray))
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(accent
                          ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(configuration.isPressed ? 0.35 : 0.18)
                          : Color.white.opacity(configuration.isPressed ? 0.1 : 0.05))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(accent ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(0.4) : Color.white.opacity(0.1), lineWidth: 1)
            )
    }
}

struct FooterButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 10, weight: .semibold))
            .foregroundColor(configuration.isPressed ? Color(red: 0.65, green: 0.71, blue: 0.99) : Color(nsColor: .systemGray))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color.white.opacity(configuration.isPressed ? 0.08 : 0.04))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.white.opacity(0.07), lineWidth: 1)
            )
    }
}
