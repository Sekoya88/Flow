import SwiftUI

private let SKILL_API = "http://localhost:18000/api/v1/local"

struct SkillNode {
    let id: String
    let name: String
    var score: Double  // 0..1 bandit reward
    var active: Bool
}

struct SkillGraphView: View {
    let wsSkills: [SkillNode]   // live from WebSocket events
    let agentId:  String?       // for DB fallback when idle

    @State private var dbSkills: [SkillNode] = []

    private static let positions: [CGPoint] = [
        CGPoint(x: 0,   y: 0),
        CGPoint(x: 68,  y: 0),
        CGPoint(x: -68, y: 0),
        CGPoint(x: 0,   y: 52),
        CGPoint(x: 0,   y: -52),
        CGPoint(x: 54,  y: 42),
        CGPoint(x: -54, y: 42),
        CGPoint(x: 54,  y: -42),
        CGPoint(x: -54, y: -42),
        CGPoint(x: 88,  y: -28),
        CGPoint(x: -88, y: -28),
        CGPoint(x: 0,   y: -68),
    ]

    private var displaySkills: [SkillNode] { wsSkills.isEmpty ? dbSkills : wsSkills }

    var body: some View {
        Group {
            if displaySkills.isEmpty {
                emptyState
            } else {
                canvas
            }
        }
        .onAppear { fetchFromDB() }
        .onChange(of: agentId) { _ in fetchFromDB() }
    }

    private var emptyState: some View {
        VStack(spacing: 6) {
            Image(systemName: "wand.and.stars")
                .font(.system(size: 18))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.3))
            Text("No skills yet")
                .font(.system(size: 10))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.4))
            Text("Run an agent to activate skills")
                .font(.system(size: 9))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.25))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var canvas: some View {
        Canvas { ctx, size in
            let cx = size.width / 2
            let cy = size.height / 2
            let nodes = displaySkills.prefix(12).enumerated().map { (i, s) -> (SkillNode, CGPoint) in
                let base = Self.positions[i]
                return (s, CGPoint(x: cx + base.x, y: cy + base.y))
            }

            // Edges from center to each satellite
            if nodes.count > 1 {
                let center = nodes[0].1
                for (skill, pt) in nodes.dropFirst() {
                    var path = Path()
                    path.move(to: center)
                    path.addLine(to: pt)
                    let alpha: Double = skill.active ? 0.3 : 0.08
                    ctx.stroke(path,
                               with: .color(Color(red: 0.39, green: 0.4, blue: 0.96).opacity(alpha)),
                               lineWidth: skill.active ? 1.2 : 0.8)
                }
            }

            // Nodes
            for (skill, pt) in nodes {
                let r = 13.0 + skill.score * 9.0
                let alpha = skill.active ? (0.45 + skill.score * 0.45) : 0.18
                let nodeColor = skill.active
                    ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(alpha)
                    : Color(nsColor: .systemGray).opacity(0.2)
                let borderColor = skill.active
                    ? Color(red: 0.65, green: 0.71, blue: 0.99).opacity(0.6)
                    : Color(nsColor: .systemGray).opacity(0.25)

                // Glow ring for active nodes
                if skill.active {
                    let glow = Path(ellipseIn: CGRect(x: pt.x - r - 6, y: pt.y - r - 6,
                                                      width: (r + 6) * 2, height: (r + 6) * 2))
                    ctx.fill(glow, with: .color(Color(red: 0.39, green: 0.4, blue: 0.96).opacity(0.12)))
                }

                let circle = Path(ellipseIn: CGRect(x: pt.x - r, y: pt.y - r, width: r * 2, height: r * 2))
                ctx.fill(circle, with: .color(nodeColor))
                ctx.stroke(circle, with: .color(borderColor), lineWidth: 1)

                // Score bar at bottom of node
                let barW = (r * 2 - 6) * skill.score
                let barRect = CGRect(x: pt.x - r + 3, y: pt.y + r - 5, width: max(barW, 0), height: 3)
                let bar = Path(roundedRect: barRect, cornerRadius: 1.5)
                ctx.fill(bar, with: .color(
                    skill.active
                        ? Color(red: 0.65, green: 0.71, blue: 0.99).opacity(0.75)
                        : Color(nsColor: .systemGray).opacity(0.3)
                ))
            }
        }
        .overlay(labelsOverlay)
    }

    private var labelsOverlay: some View {
        GeometryReader { geo in
            let cx = geo.size.width / 2
            let cy = geo.size.height / 2
            ForEach(Array(displaySkills.prefix(12).enumerated()), id: \.offset) { i, skill in
                let base = Self.positions[i]
                let pt   = CGPoint(x: cx + base.x, y: cy + base.y)
                let label = skill.name.count > 11 ? String(skill.name.prefix(10)) + "…" : skill.name
                Text(label)
                    .font(.system(size: 7.5, weight: .semibold))
                    .foregroundColor(
                        skill.active
                            ? Color(red: 0.82, green: 0.86, blue: 1.0)
                            : Color(nsColor: .systemGray).opacity(0.45)
                    )
                    .position(pt)
            }
        }
    }

    private func fetchFromDB() {
        guard let id = agentId,
              let url = URL(string: "\(SKILL_API)/agent-skills/\(id)") else { return }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            guard let data else { return }
            let skills = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])
                .flatMap { $0["skills"] as? [[String: Any]] } ?? []
            let nodes = skills.compactMap { dict -> SkillNode? in
                guard let sid  = dict["id"]    as? String,
                      let name = dict["name"]  as? String else { return nil }
                let score = dict["score"] as? Double ?? 0.5
                return SkillNode(id: sid, name: name, score: score, active: false)
            }
            DispatchQueue.main.async { self.dbSkills = nodes }
        }.resume()
    }
}
