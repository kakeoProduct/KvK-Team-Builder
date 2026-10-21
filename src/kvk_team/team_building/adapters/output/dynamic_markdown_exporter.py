"""時間帯別配置と交代差分をMarkdownへ出力する。"""

from dataclasses import dataclass

from kvk_team.team_building.domain.member import MINUTES_PER_HOUR
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.schedule import SlotAssignment
from kvk_team.team_building.domain.team_master import TeamDefinition
from kvk_team.team_building.domain.validation import (
    DynamicValidationCode,
    DynamicValidationIssue,
    DynamicValidationReport,
    ValidatedTeamPlan,
)


@dataclass(slots=True)
class DynamicMarkdownExporter:
    """初期配置、交代、指標、待機、自己チェックを出力する。"""

    rules: KvKRules

    def export(self, validated: ValidatedTeamPlan) -> str:
        """検証済みの動的チーム編成を運用可能なMarkdownとして返す。"""

        plan = validated.plan
        report = validated.report
        sections = [
            self._render_team(plan.assignments_for_team(definition.label), definition)
            for definition in self.rules.team_master.teams
        ]
        sections.append(self._render_standby(report))
        sections.append(self._render_metrics(report))
        sections.append(self._render_self_check(report))
        return "\n\n".join(sections).rstrip() + "\n"

    def _render_team(
        self,
        assignments: tuple[SlotAssignment, ...],
        definition: TeamDefinition,
    ) -> str:
        """1チームの初期配置と時刻別の交代差分を描画する。"""

        first = assignments[0]
        peak_count = max(len(assignment.members) for assignment in assignments)
        lines = [
            f"## {definition.label.value}（{definition.role}）（最大{peak_count}）",
            "",
        ]
        if definition.notes:
            lines.extend(f"> {note}" for note in definition.notes)
            lines.append("")
        start_time = self._format_clock(first.time_slot.start_minutes)
        lines.append(f"### {start_time} 初期配置")
        lines.append("")
        lines.extend(member.name for member in first.members)
        previous_names = set(first.member_names())
        for assignment in assignments[1:]:
            current_names = set(assignment.member_names())
            leaving = sorted(previous_names - current_names)
            joining = sorted(current_names - previous_names)
            if leaving or joining:
                change_time = self._format_clock(assignment.time_slot.start_minutes)
                lines.extend(("", f"### {change_time} 交代", ""))
                if leaving:
                    lines.append("- 退出: " + "、".join(leaving))
                if joining:
                    lines.append("- 参加: " + "、".join(joining))
            previous_names = current_names
        return "\n".join(lines)

    def _render_standby(self, report: DynamicValidationReport) -> str:
        """開始時刻が確定していない今回の待機メンバーを描画する。"""

        lines = ["## 時間確定待ち", ""]
        if not report.standby_members:
            lines.append("なし")
            return "\n".join(lines)
        leaders = {
            definition.rally_leader: definition.label
            for definition in self.rules.team_master.teams
        }
        for member in report.standby_members:
            team_label = leaders.get(member.name)
            suffix = (
                f"（到着後は{team_label.value}の固定集結主）"
                if team_label is not None
                else "（到着時に再最適化）"
            )
            lines.append(f"- {member.name}{suffix}")
        return "\n".join(lines)

    def _render_metrics(self, report: DynamicValidationReport) -> str:
        """時間帯別の人数、戦力、VC、集結主を描画する。"""

        lines = [
            "## 時間帯別チーム集計",
            "",
            "| 時刻 | チーム | 人数 | 戦力 | VC | 集結主 |",
            "|---|---|---:|---:|---:|---|",
        ]
        for metric in report.slot_metrics:
            lines.append(
                f"| {self._format_clock(metric.time_slot.start_minutes)} | "
                f"{metric.team_label.value} | {metric.member_count} | "
                f"{metric.power} | {metric.vc_count} | "
                f"{metric.leader_name or '到着待ち'} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _render_self_check(report: DynamicValidationReport) -> str:
        """必須条件と警告を分離した自己チェックを描画する。"""

        issue_codes = {issue.code for issue in report.issues}
        lines = [
            "## 自己チェック",
            "",
            f"- 必須条件: {'OK' if report.is_valid else 'NG'}",
            "- 確定参加者の重複: "
            + ("NG" if DynamicValidationCode.DUPLICATE in issue_codes else "OK"),
            "- 確定参加者の未配置: "
            + ("NG" if DynamicValidationCode.UNASSIGNED in issue_codes else "OK"),
            f"- 時間確定待ち: {len(report.standby_members)}人",
            f"- 警告: {len(report.warnings)}件",
        ]
        if report.issues:
            lines.extend(("", "### NG詳細", ""))
            lines.extend(
                f"- {DynamicMarkdownExporter._issue_text(issue)}"
                for issue in report.issues
            )
        if report.warnings:
            lines.extend(("", "### 警告詳細", ""))
            lines.extend(
                f"- {DynamicMarkdownExporter._issue_text(warning)}"
                for warning in report.warnings
            )
        return "\n".join(lines)

    @staticmethod
    def _issue_text(issue: DynamicValidationIssue) -> str:
        """検証結果へ対象時刻を付けて運用上の発生箇所を明示する。"""

        if issue.time_slot is None:
            return issue.message
        time_text = DynamicMarkdownExporter._format_clock(issue.time_slot.start_minutes)
        return f"{time_text}: {issue.message}"

    @staticmethod
    def _format_clock(minutes: int) -> str:
        """分単位の時刻を`HH:MM`へ変換する。"""

        hour, minute = divmod(minutes, MINUTES_PER_HOUR)
        return f"{hour:02d}:{minute:02d}"
