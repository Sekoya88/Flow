import SwiftUI

struct EventFeedView: View {
    let events: [AgentEvent]

    var body: some View {
        if events.isEmpty {
            Text("Waiting for events…")
                .font(.system(size: 11))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.5))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 8)
        } else {
            ScrollView(.vertical, showsIndicators: false) {
                LazyVStack(spacing: 3) {
                    ForEach(events) { event in
                        EventRowView(event: event, isLatest: event.id == events.first?.id)
                    }
                }
            }
        }
    }
}

struct EventRowView: View {
    let event: AgentEvent
    let isLatest: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 6) {
            Image(systemName: iconName)
                .font(.system(size: 11))
                .foregroundColor(iconColor)
                .frame(width: 14)
                .padding(.top, 1)
            VStack(alignment: .leading, spacing: 2) {
                Text(event.description)
                    .font(.system(size: 11))
                    .foregroundColor(isLatest ? Color(nsColor: .labelColor) : Color(nsColor: .secondaryLabelColor))
                    .lineLimit(2)
                Text(event.timestamp, style: .relative)
                    .font(.system(size: 9))
                    .foregroundColor(Color(nsColor: .tertiaryLabelColor))
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 3)
        .background(isLatest ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(0.07) : Color.clear)
        .clipShape(RoundedRectangle(cornerRadius: 5))
    }

    private var iconName: String {
        switch event.type {
        case "skills_matched":          return "wand.and.stars"
        case "metacog_evaluated":       return "brain"
        case "skill_arm_updated":       return "chart.bar.fill"
        case "connection_established":  return "antenna.radiowaves.left.and.right"
        default:                        return "circle.fill"
        }
    }

    private var iconColor: Color {
        switch event.type {
        case "skills_matched":   return Color(red: 0.51, green: 0.55, blue: 0.97)
        case "metacog_evaluated":
            let grade = event.payload["grade"] as? Int ?? 3
            if grade <= 2 { return .red }
            if grade == 3 { return .yellow }
            return .green
        case "skill_arm_updated": return .blue
        case "connection_established": return .green
        default: return Color(nsColor: .systemGray)
        }
    }
}
