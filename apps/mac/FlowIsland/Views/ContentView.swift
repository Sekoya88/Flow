import SwiftUI
import AppKit

private let WEB_APP          = "http://localhost:13000"
private let API_BASE         = "http://localhost:18000/api/v1/local"
private let PILL_W:  CGFloat = 200
private let PILL_H:  CGFloat = 37
private let PANEL_W: CGFloat = 540
private let PANEL_H: CGFloat = 500

// MARK: - Root

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
    @State private var showAgentPicker = false

    private var isOpen:     Bool { store.notchState     == .open }
    private var isHovering: Bool { store.isHoveringPill && !isOpen }

    var body: some View {
        VStack(spacing: 0) {
            pillRow.frame(height: PILL_H)
            panelBody
                .frame(height: PANEL_H - PILL_H)
                .opacity(isOpen ? 1 : 0)
                .animation(
                    isOpen ? .easeIn(duration: 0.12).delay(0.08) : .easeOut(duration: 0.08),
                    value: isOpen
                )
        }
        .frame(
            width:  isOpen ? PANEL_W : PILL_W,
            height: isOpen ? PANEL_H  : PILL_H,
            alignment: .top
        )
        .background(Color.black)
        .clipShape(NotchShape(topRadius: isOpen ? 20 : 8, bottomRadius: isOpen ? 24 : 20))
        .shadow(
            color: isHovering ? .white.opacity(0.18) : (isOpen ? .black.opacity(0.55) : .clear),
            radius: isHovering ? 12 : 22,
            y: isHovering ? 0 : 12
        )
        .scaleEffect(isHovering ? 1.05 : 1.0)
        .animation(
            isHovering ? .spring(response: 0.18, dampingFraction: 0.65)
                       : .spring(response: 0.45, dampingFraction: 1.0),
            value: isHovering
        )
        .animation(
            isOpen ? .spring(response: 0.42, dampingFraction: 0.8)
                   : .spring(response: 0.45, dampingFraction: 1.0),
            value: store.notchState
        )
    }

    // MARK: Pill row

    private var pillRow: some View {
        HStack(spacing: 7) {
            Circle()
                .fill(store.wsClient.isConnected ? Color.green : Color(nsColor: .systemGray))
                .frame(width: 7, height: 7)
                .shadow(color: store.wsClient.isConnected ? .green.opacity(0.8) : .clear, radius: 4)
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

    // MARK: Expanded panel

    private var panelBody: some View {
        VStack(spacing: 0) {
            headerRow
            if !store.wsClient.isConnected { noAgentBanner }
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
            // Status dot
            Circle()
                .fill(store.wsClient.isConnected ? Color.green : Color(nsColor: .systemGray).opacity(0.4))
                .frame(width: 7, height: 7)
                .shadow(color: store.wsClient.isConnected ? .green.opacity(0.7) : .clear, radius: 4)

            Text("Flow")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(.white)

            // Agent name — clickable picker
            Button(action: { showAgentPicker.toggle() }) {
                HStack(spacing: 3) {
                    Text(store.wsClient.agentName
                         ?? (store.wsClient.currentAgentId.map { String($0.prefix(8)) + "…" })
                         ?? "No agent")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundColor(.white.opacity(0.65))
                    Image(systemName: "chevron.down")
                        .font(.system(size: 7, weight: .bold))
                        .foregroundColor(.white.opacity(0.3))
                }
                .padding(.horizontal, 7)
                .padding(.vertical, 3)
                .background(Color.white.opacity(0.07))
                .clipShape(Capsule())
                .overlay(Capsule().stroke(Color.white.opacity(0.12), lineWidth: 1))
            }
            .buttonStyle(PlainButtonStyle())
            .popover(isPresented: $showAgentPicker, arrowEdge: .bottom) {
                agentPickerPopover
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

    // MARK: Agent picker popover

    private var agentPickerPopover: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("AGENTS")
                .font(.system(size: 8, weight: .bold))
                .foregroundColor(Color(nsColor: .systemGray))
                .tracking(1.5)
                .padding(.horizontal, 14)
                .padding(.top, 12)
                .padding(.bottom, 6)

            if store.availableAgents.isEmpty {
                Text("No agents found")
                    .font(.system(size: 11))
                    .foregroundColor(Color(nsColor: .secondaryLabelColor))
                    .padding(.horizontal, 14)
                    .padding(.bottom, 12)
            } else {
                ForEach(store.availableAgents) { agent in
                    Button(action: {
                        store.wsClient.connect(agentId: agent.id, name: agent.name)
                        showAgentPicker = false
                    }) {
                        HStack(spacing: 9) {
                            Circle()
                                .fill(agent.id == store.wsClient.currentAgentId
                                      ? Color.green : Color(nsColor: .systemGray).opacity(0.4))
                                .frame(width: 6, height: 6)
                            Text(agent.name)
                                .font(.system(size: 12))
                                .foregroundColor(.primary)
                            Spacer()
                            if agent.id == store.wsClient.currentAgentId {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 10, weight: .semibold))
                                    .foregroundColor(.green)
                            }
                        }
                        .padding(.horizontal, 14)
                        .padding(.vertical, 7)
                        .background(agent.id == store.wsClient.currentAgentId
                                    ? Color.accentColor.opacity(0.1) : Color.clear)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
        }
        .frame(minWidth: 220)
        .padding(.bottom, 8)
    }

    // MARK: State badge / buttons

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

    // MARK: Overview tab

    private var overviewContent: some View {
        VStack(spacing: 0) {
            skillGraphSection
            Divider().opacity(0.15).padding(.horizontal, 16)
            eventFeedSection
        }
    }

    private var skillGraphSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                sectionLabel("Skill graph")
                Spacer()
                if !store.wsClient.skills.isEmpty {
                    Text("LIVE")
                        .font(.system(size: 7, weight: .bold))
                        .foregroundColor(.green)
                        .tracking(1)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 2)
                        .background(Color.green.opacity(0.12))
                        .clipShape(Capsule())
                }
            }
            SkillGraphView(wsClient: store.wsClient)
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
        let id: String
        let status: String
        let message: String
        let createdAt: String
        let completedAt: String

        var statusIcon: String {
            switch status {
            case "completed":          return "checkmark.circle.fill"
            case "running":            return "bolt.fill"
            case "failed", "error":    return "xmark.circle.fill"
            default:                   return "circle"
            }
        }

        var statusColor: Color {
            switch status {
            case "completed":          return .green
            case "running":            return Color(red: 0.23, green: 0.51, blue: 0.96)
            case "failed", "error":    return Color(red: 0.96, green: 0.3, blue: 0.3)
            default:                   return Color(nsColor: .systemGray)
            }
        }

        var duration: String {
            guard let start = parseISO(createdAt) else { return "" }
            let end: Date = completedAt.isEmpty ? Date() : (parseISO(completedAt) ?? Date())
            let secs = Int(end.timeIntervalSince(start))
            if secs <= 0 { return "" }
            return secs < 60 ? "\(secs)s" : "\(secs / 60)m \(secs % 60)s"
        }

        var relativeTime: String {
            guard let date = parseISO(createdAt) else { return "" }
            let diff = -date.timeIntervalSinceNow
            if diff < 60  { return "just now" }
            if diff < 3600 { return "\(Int(diff / 60))m ago" }
            if diff < 86400 { return "\(Int(diff / 3600))h ago" }
            return "\(Int(diff / 86400))d ago"
        }
    }

    @State private var runs: [RunRow] = []
    @State private var loading = true

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                sectionLabel("Recent runs")
                Spacer()
                if loading { ProgressView().scaleEffect(0.5) }
                else {
                    Text("\(runs.count) run\(runs.count == 1 ? "" : "s")")
                        .font(.system(size: 9))
                        .foregroundColor(Color(nsColor: .systemGray).opacity(0.5))
                }
            }

            if runs.isEmpty && !loading {
                emptyState(icon: "play.circle", title: "No runs yet",
                           subtitle: "Trigger an agent to see execution history")
            } else {
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: 5) {
                        ForEach(runs) { run in RunRowView(run: run) }
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
                        id:          $0["id"]           as? String ?? "",
                        status:      $0["status"]        as? String ?? "unknown",
                        message:     $0["message"]       as? String ?? "",
                        createdAt:   $0["created_at"]    as? String ?? "",
                        completedAt: $0["completed_at"]  as? String ?? ""
                    )
                }
                loading = false
            }
        }.resume()
    }
}

struct RunRowView: View {
    let run: RunsTabView.RunRow

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 7) {
                Image(systemName: run.statusIcon)
                    .font(.system(size: 10))
                    .foregroundColor(run.statusColor)
                    .frame(width: 14)

                Text(run.message.isEmpty ? "(no message)" : run.message)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(.white.opacity(0.88))
                    .lineLimit(1)

                Spacer()

                Text(run.relativeTime)
                    .font(.system(size: 9))
                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.55))
            }

            HStack(spacing: 8) {
                Text(run.status.uppercased())
                    .font(.system(size: 8, weight: .bold))
                    .foregroundColor(run.statusColor)
                    .tracking(0.8)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1.5)
                    .background(run.statusColor.opacity(0.1))
                    .clipShape(Capsule())

                if !run.duration.isEmpty {
                    HStack(spacing: 3) {
                        Image(systemName: "clock")
                            .font(.system(size: 7))
                        Text(run.duration)
                            .font(.system(size: 9))
                    }
                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.5))
                }

                Spacer()

                Text(String(run.id.prefix(8)))
                    .font(.system(size: 8, design: .monospaced))
                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.3))
            }
            .padding(.leading, 21)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(Color.white.opacity(0.04))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.white.opacity(0.06), lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Memory tab  (Vibe coding: skills + knowledge + rules)

struct MemoryTabView: View {
    let agentId: String?

    struct MemRow: Identifiable {
        let id, content, createdAt: String
        var relativeTime: String {
            guard let date = parseISO(createdAt) else { return "" }
            let diff = -date.timeIntervalSinceNow
            if diff < 60    { return "just now" }
            if diff < 3600  { return "\(Int(diff / 60))m ago" }
            if diff < 86400 { return "\(Int(diff / 3600))h ago" }
            return "\(Int(diff / 86400))d ago"
        }
    }

    struct SkillChip: Identifiable {
        let id, name: String
        let score: Double
        let useCount: Int
        let category: String
    }

    @State private var memories:      [MemRow]    = []
    @State private var skills:        [SkillChip] = []
    @State private var loadingMem     = true
    @State private var loadingSkills  = true
    @State private var showAddSkill   = false
    @State private var showAddKnow    = false
    @State private var showAddRule    = false

    var body: some View {
        VStack(spacing: 0) {
            ScrollView(.vertical, showsIndicators: false) {
                VStack(alignment: .leading, spacing: 12) {

                    // ── Skills ────────────────────────────────────
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            sectionLabel("Skills")
                            Spacer()
                            if loadingSkills {
                                ProgressView().scaleEffect(0.45)
                            } else {
                                Text("\(skills.count) skill\(skills.count == 1 ? "" : "s")")
                                    .font(.system(size: 8))
                                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.4))
                            }
                        }
                        if skills.isEmpty && !loadingSkills {
                            Text("No skills configured for this agent")
                                .font(.system(size: 10))
                                .foregroundColor(Color(nsColor: .systemGray).opacity(0.4))
                                .padding(.top, 2)
                        } else {
                            let categoryOrder = ["Research","Code","Communication","Analysis","Memory","Planning","General"]
                            let groups: [(String, [SkillChip])] = {
                                var map = [(String, [SkillChip])]()
                                for skill in skills {
                                    if let idx = map.firstIndex(where: { $0.0 == skill.category }) {
                                        map[idx].1.append(skill)
                                    } else {
                                        map.append((skill.category, [skill]))
                                    }
                                }
                                return map.sorted {
                                    let ia = categoryOrder.firstIndex(of: $0.0) ?? 99
                                    let ib = categoryOrder.firstIndex(of: $1.0) ?? 99
                                    return ia < ib
                                }
                            }()
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(groups, id: \.0) { cat, catSkills in
                                    VStack(alignment: .leading, spacing: 5) {
                                        HStack(spacing: 4) {
                                            Text(cat.uppercased())
                                                .font(.system(size: 7.5, weight: .bold, design: .monospaced))
                                                .foregroundColor(Color(nsColor: .systemGray).opacity(0.45))
                                                .tracking(1.0)
                                            Text("·  \(catSkills.count)")
                                                .font(.system(size: 7.5, design: .monospaced))
                                                .foregroundColor(Color(nsColor: .systemGray).opacity(0.25))
                                        }
                                        LazyVGrid(columns: [
                                            GridItem(.flexible(), spacing: 6),
                                            GridItem(.flexible(), spacing: 6),
                                        ], spacing: 6) {
                                            ForEach(catSkills) { skill in SkillChipView(chip: skill) }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Divider().opacity(0.12)

                    // ── Episodic Memory / Rules ───────────────────
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            sectionLabel("Memory & Rules")
                            Spacer()
                            if loadingMem {
                                ProgressView().scaleEffect(0.45)
                            } else if !memories.isEmpty {
                                Text("\(memories.count) entr\(memories.count == 1 ? "y" : "ies")")
                                    .font(.system(size: 8))
                                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.4))
                            }
                        }
                        if memories.isEmpty && !loadingMem {
                            VStack(spacing: 5) {
                                Image(systemName: "brain")
                                    .font(.system(size: 18))
                                    .foregroundColor(Color(red: 0.65, green: 0.55, blue: 0.98).opacity(0.25))
                                Text("No memories yet")
                                    .font(.system(size: 10, weight: .medium))
                                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.4))
                                Text("Written during metacognition cycles")
                                    .font(.system(size: 9))
                                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.25))
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.top, 8)
                        } else {
                            VStack(spacing: 5) {
                                ForEach(memories) { mem in MemRowView(mem: mem) }
                            }
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 10)
                .padding(.bottom, 8)
            }

            // ── Vibe coding toolbar ───────────────────────────────
            Divider().opacity(0.1)
            HStack(spacing: 8) {
                vibeButton(icon: "bolt.fill", label: "Skill",
                           color: Color(red: 0.133, green: 0.827, blue: 0.933)) {
                    showAddSkill = true
                }
                vibeButton(icon: "doc.text.fill", label: "Knowledge",
                           color: Color(red: 0.133, green: 0.773, blue: 0.368)) {
                    showAddKnow = true
                }
                vibeButton(icon: "brain", label: "Rule / Memory",
                           color: Color(red: 0.655, green: 0.545, blue: 0.973)) {
                    showAddRule = true
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
        }
        .frame(maxHeight: .infinity)
        .onAppear { fetchAll() }
        .onChange(of: agentId) { _ in fetchAll() }
        .sheet(isPresented: $showAddSkill, onDismiss: fetchAll) {
            AddSkillSheet(agentId: agentId ?? "")
        }
        .sheet(isPresented: $showAddKnow, onDismiss: fetchAll) {
            AddKnowledgeSheet(agentId: agentId ?? "")
        }
        .sheet(isPresented: $showAddRule, onDismiss: fetchAll) {
            AddRuleSheet(agentId: agentId ?? "")
        }
    }

    // MARK: Vibe button

    private func vibeButton(icon: String, label: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(color.opacity(0.85))
                Text("+ \(label)")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(color.opacity(0.85))
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(color.opacity(0.08))
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(color.opacity(0.22), lineWidth: 1))
            .cornerRadius(6)
        }
        .buttonStyle(.plain)
        .disabled(agentId == nil)
    }

    // MARK: Fetch

    private func fetchAll() {
        fetchMemory()
        fetchSkills()
    }

    private func fetchMemory() {
        guard let id = agentId else { loadingMem = false; return }
        guard let url = URL(string: "\(API_BASE)/agent-memory/\(id)") else { return }
        loadingMem = true
        URLSession.shared.dataTask(with: url) { data, _, _ in
            let rows = (try? JSONSerialization.jsonObject(with: data ?? Data()) as? [String: Any])
                .flatMap { $0["memories"] as? [[String: Any]] } ?? []
            DispatchQueue.main.async {
                memories   = rows.map { MemRow(id: $0["id"] as? String ?? "",
                                               content: $0["content"] as? String ?? "",
                                               createdAt: $0["created_at"] as? String ?? "") }
                loadingMem = false
            }
        }.resume()
    }

    private func fetchSkills() {
        guard let id = agentId else { loadingSkills = false; return }
        guard let url = URL(string: "\(API_BASE)/agent-skills/\(id)") else { return }
        loadingSkills = true
        URLSession.shared.dataTask(with: url) { data, _, _ in
            let rows = (try? JSONSerialization.jsonObject(with: data ?? Data()) as? [String: Any])
                .flatMap { $0["skills"] as? [[String: Any]] } ?? []
            DispatchQueue.main.async {
                skills = rows.map { SkillChip(id: $0["id"] as? String ?? "",
                                              name: $0["name"] as? String ?? "",
                                              score: $0["score"] as? Double ?? 0,
                                              useCount: $0["use_count"] as? Int ?? 0,
                                              category: $0["category"] as? String ?? "General") }
                loadingSkills = false
            }
        }.resume()
    }
}

// MARK: - Add Skill sheet

struct AddSkillSheet: View {
    let agentId: String
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var contentMd = "## Description\n\nDescribe what this skill does.\n\n## Instructions\n\n1. "
    @State private var saving = false
    @State private var errorMsg: String?

    private let cyan = Color(red: 0.133, green: 0.827, blue: 0.933)

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: "bolt.fill").foregroundColor(cyan.opacity(0.8))
                    Text("New Skill")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(.white)
                }
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(GlassButtonStyle(accent: false))
            }

            TextField("Skill name (e.g. content-brief-generation)", text: $name)
                .textFieldStyle(.plain)
                .font(.system(size: 11, weight: .medium))
                .foregroundColor(.white)
                .padding(8)
                .background(Color.white.opacity(0.05))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color.white.opacity(0.08), lineWidth: 1))
                .cornerRadius(6)

            VStack(alignment: .leading, spacing: 4) {
                Text("Skill instructions (Markdown)")
                    .font(.system(size: 9))
                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.5))
                TextEditor(text: $contentMd)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.white.opacity(0.85))
                    .scrollContentBackground(.hidden)
                    .padding(8)
                    .background(Color.white.opacity(0.04))
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color.white.opacity(0.07), lineWidth: 1))
                    .cornerRadius(6)
                    .frame(minHeight: 180)
            }

            if let err = errorMsg {
                Text(err).font(.system(size: 9)).foregroundColor(.red.opacity(0.8))
            }

            HStack {
                Spacer()
                Button(saving ? "Saving…" : "Save Skill") { save() }
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || contentMd.isEmpty || saving)
                    .buttonStyle(GlassButtonStyle(accent: true))
            }
        }
        .padding(20)
        .frame(width: 500, height: 400)
        .background(Color(red: 0.06, green: 0.06, blue: 0.10))
    }

    private func save() {
        saving = true; errorMsg = nil
        guard let url = URL(string: "http://localhost:18000/api/v1/local/agent-skills") else { return }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: [
            "agent_id": agentId, "name": name.trimmingCharacters(in: .whitespaces), "content_md": contentMd
        ])
        URLSession.shared.dataTask(with: req) { data, _, err in
            DispatchQueue.main.async {
                saving = false
                if err != nil { errorMsg = "Network error"; return }
                if let json = try? JSONSerialization.jsonObject(with: data ?? Data()) as? [String: Any],
                   let e = json["error"] as? String { errorMsg = e; return }
                dismiss()
            }
        }.resume()
    }
}

// MARK: - Add Knowledge sheet

struct AddKnowledgeSheet: View {
    let agentId: String
    @Environment(\.dismiss) private var dismiss

    @State private var title = ""
    @State private var content = ""
    @State private var saving = false
    @State private var errorMsg: String?

    private let green = Color(red: 0.133, green: 0.773, blue: 0.368)

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: "doc.text.fill").foregroundColor(green.opacity(0.8))
                    Text("Ingest Knowledge")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(.white)
                }
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(GlassButtonStyle(accent: false))
            }

            TextField("Title or URL", text: $title)
                .textFieldStyle(.plain)
                .font(.system(size: 11, weight: .medium))
                .foregroundColor(.white)
                .padding(8)
                .background(Color.white.opacity(0.05))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color.white.opacity(0.08), lineWidth: 1))
                .cornerRadius(6)

            VStack(alignment: .leading, spacing: 4) {
                Text("Content (paste text, code, docs…)")
                    .font(.system(size: 9))
                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.5))
                TextEditor(text: $content)
                    .font(.system(size: 10))
                    .foregroundColor(.white.opacity(0.85))
                    .scrollContentBackground(.hidden)
                    .padding(8)
                    .background(Color.white.opacity(0.04))
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color.white.opacity(0.07), lineWidth: 1))
                    .cornerRadius(6)
                    .frame(minHeight: 160)
            }

            if let err = errorMsg {
                Text(err).font(.system(size: 9)).foregroundColor(.red.opacity(0.8))
            }

            HStack {
                Spacer()
                Button(saving ? "Ingesting…" : "Ingest") { save() }
                    .disabled(content.trimmingCharacters(in: .whitespaces).isEmpty || saving)
                    .buttonStyle(GlassButtonStyle(accent: true))
            }
        }
        .padding(20)
        .frame(width: 500, height: 380)
        .background(Color(red: 0.06, green: 0.06, blue: 0.10))
    }

    private func save() {
        saving = true; errorMsg = nil
        guard let url = URL(string: "http://localhost:18000/api/v1/local/agent-knowledge") else { return }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: [
            "agent_id": agentId,
            "title": title.isEmpty ? "Knowledge" : title,
            "content": content.trimmingCharacters(in: .whitespaces),
        ])
        URLSession.shared.dataTask(with: req) { data, _, err in
            DispatchQueue.main.async {
                saving = false
                if err != nil { errorMsg = "Network error"; return }
                if let json = try? JSONSerialization.jsonObject(with: data ?? Data()) as? [String: Any],
                   let e = json["error"] as? String { errorMsg = e; return }
                dismiss()
            }
        }.resume()
    }
}

// MARK: - Add Rule / Memory sheet

struct AddRuleSheet: View {
    let agentId: String
    @Environment(\.dismiss) private var dismiss

    @State private var content = ""
    @State private var saving = false
    @State private var errorMsg: String?

    private let violet = Color(red: 0.655, green: 0.545, blue: 0.973)

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: "brain").foregroundColor(violet.opacity(0.8))
                    Text("Add Rule or Memory")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(.white)
                }
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(GlassButtonStyle(accent: false))
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Rule, fact, or memory the agent should always know")
                    .font(.system(size: 9))
                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.5))
                ZStack(alignment: .topLeading) {
                    if content.isEmpty {
                        Text("e.g. Always respond in French. Never mention competitor pricing.")
                            .font(.system(size: 10))
                            .foregroundColor(Color(nsColor: .systemGray).opacity(0.3))
                            .padding(.top, 10)
                            .padding(.leading, 10)
                            .allowsHitTesting(false)
                    }
                    TextEditor(text: $content)
                        .font(.system(size: 10))
                        .foregroundColor(.white.opacity(0.9))
                        .scrollContentBackground(.hidden)
                        .padding(8)
                }
                .background(Color.white.opacity(0.04))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color.white.opacity(0.07), lineWidth: 1))
                .cornerRadius(6)
                .frame(minHeight: 140)
            }

            if let err = errorMsg {
                Text(err).font(.system(size: 9)).foregroundColor(.red.opacity(0.8))
            }

            HStack {
                Spacer()
                Button(saving ? "Saving…" : "Save") { save() }
                    .disabled(content.trimmingCharacters(in: .whitespaces).isEmpty || saving)
                    .buttonStyle(GlassButtonStyle(accent: true))
            }
        }
        .padding(20)
        .frame(width: 480, height: 320)
        .background(Color(red: 0.06, green: 0.06, blue: 0.10))
    }

    private func save() {
        saving = true; errorMsg = nil
        guard let url = URL(string: "http://localhost:18000/api/v1/local/agent-memory") else { return }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: [
            "agent_id": agentId,
            "content": content.trimmingCharacters(in: .whitespaces),
        ])
        URLSession.shared.dataTask(with: req) { data, _, err in
            DispatchQueue.main.async {
                saving = false
                if err != nil { errorMsg = "Network error"; return }
                if let json = try? JSONSerialization.jsonObject(with: data ?? Data()) as? [String: Any],
                   let e = json["error"] as? String { errorMsg = e; return }
                dismiss()
            }
        }.resume()
    }
}

struct SkillChipView: View {
    let chip: MemoryTabView.SkillChip

    private let cyan = Color(red: 0.133, green: 0.827, blue: 0.933)

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
                Circle()
                    .fill(cyan.opacity(0.7))
                    .frame(width: 5, height: 5)
                Text(chip.name)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(cyan.opacity(0.9))
                    .lineLimit(1)
            }
            // Score bar
            RoundedRectangle(cornerRadius: 2)
                .fill(Color.white.opacity(0.06))
                .frame(height: 3)
                .overlay(
                    GeometryReader { g in
                        RoundedRectangle(cornerRadius: 2)
                            .fill(cyan.opacity(0.55))
                            .frame(width: g.size.width * chip.score)
                    },
                    alignment: .leading
                )
            HStack {
                Text(String(format: "%.0f%%", chip.score * 100))
                    .font(.system(size: 8, design: .monospaced))
                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.5))
                Spacer()
                if chip.useCount > 0 {
                    Text("×\(chip.useCount)")
                        .font(.system(size: 8))
                        .foregroundColor(Color(nsColor: .systemGray).opacity(0.4))
                }
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 7)
        .background(cyan.opacity(0.05))
        .overlay(RoundedRectangle(cornerRadius: 7)
            .stroke(cyan.opacity(0.18), lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 7))
    }
}

struct MemRowView: View {
    let mem: MemoryTabView.MemRow
    private let violet = Color(red: 0.655, green: 0.545, blue: 0.973)

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            ZStack {
                Circle().fill(violet.opacity(0.1)).frame(width: 22, height: 22)
                Image(systemName: "brain")
                    .font(.system(size: 9))
                    .foregroundColor(violet.opacity(0.8))
            }
            .padding(.top, 1)

            VStack(alignment: .leading, spacing: 3) {
                Text(mem.content)
                    .font(.system(size: 10))
                    .foregroundColor(.white.opacity(0.82))
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
                if !mem.relativeTime.isEmpty {
                    Text(mem.relativeTime)
                        .font(.system(size: 8))
                        .foregroundColor(Color(nsColor: .systemGray).opacity(0.4))
                }
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(violet.opacity(0.04))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(violet.opacity(0.12), lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Shared helpers

private func sectionLabel(_ text: String) -> some View {
    Text(text.uppercased())
        .font(.system(size: 9, weight: .bold))
        .foregroundColor(Color(nsColor: .systemGray).opacity(0.7))
        .tracking(1.2)
}

private func emptyState(icon: String, title: String, subtitle: String) -> some View {
    VStack(spacing: 6) {
        Image(systemName: icon)
            .font(.system(size: 20))
            .foregroundColor(Color(nsColor: .systemGray).opacity(0.25))
        Text(title)
            .font(.system(size: 11, weight: .medium))
            .foregroundColor(Color(nsColor: .systemGray).opacity(0.5))
        Text(subtitle)
            .font(.system(size: 9))
            .foregroundColor(Color(nsColor: .systemGray).opacity(0.3))
            .multilineTextAlignment(.center)
    }
    .frame(maxWidth: .infinity)
    .padding(.top, 20)
}

private func parseISO(_ str: String) -> Date? {
    guard !str.isEmpty else { return nil }
    let fmt = ISO8601DateFormatter()
    fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let d = fmt.date(from: str) { return d }
    fmt.formatOptions = [.withInternetDateTime]
    return fmt.date(from: str)
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
