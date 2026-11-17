"""所属固定の編成をMarkdownへ出力する。

チャット共有用テキスト（OUT-001〜OUT-014）はIssue 6で置き換える。それまでは、隊ごとの所属、
出撃開始時刻、応援、時間帯別の出撃、待機、別枠、注記、自己チェックを運用者が確かめられる形で出す。
"""

from dataclasses import dataclass

from kvk_team.team_building.domain.availability import AvailabilityResolver
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.plan import TeamMembership, TeamPlan
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.team import team_name
from kvk_team.team_building.domain.validation import (
    SortieMetrics,
    ValidatedTeamPlan,
    ValidationCode,
    ValidationIssue,
    ValidationReport,
    format_clock,
)


def _leader_cell(metric: SortieMetrics) -> str:
    """出撃表のリーダーの欄。

    出撃開始前は「出撃開始前」、所属メンバーが0人なら「休止」と書く（FRM-041、FRM-048のA-06）。
    休止は応援を含めずに判定する。
    """

    if not metric.started:
        return "出撃開始前"
    if metric.member_count - metric.support_count == 0:
        return "休止"
    return metric.leader_name or "不在"


def _count_cell(metric: SortieMetrics) -> str:
    """出撃人数の欄。応援を受けた時間帯は応援の人数を添える（FRM-042）。"""

    if metric.support_count:
        return f"{metric.member_count}（応援{metric.support_count}）"
    return str(metric.member_count)


@dataclass(slots=True)
class TeamPlanMarkdownExporter:
    """隊、出撃、待機、別枠、自己チェックを出力する。"""

    rules: KvKRules

    def export(self, validated: ValidatedTeamPlan) -> str:
        """検証済みの編成を運用可能なMarkdownとして返す。"""

        plan = validated.plan
        report = validated.report
        undecided_leaders = {
            membership.leader: membership.number
            for membership in plan.teams
            if not membership.leader_is_member
        }
        sections = [self._render_team(membership) for membership in plan.teams]
        if plan.supports:
            sections.append(self._render_supports(plan))
        sections.append(self._render_waiting(report))
        sections.append(self._render_undecided(report, undecided_leaders))
        sections.append(self._render_metrics(report))
        if validated.notes:
            sections.append(self._render_notes(validated.notes))
        sections.append(self._render_self_check(report))
        return "\n\n".join(sections).rstrip() + "\n"

    def _render_team(self, membership: TeamMembership) -> str:
        """1つの隊の見出しと所属メンバーを描画する（OUT-001）。"""

        name = team_name(membership.number)
        heading = (
            f"## {name} リーダー: {membership.leader.name}"
            if membership.leader_is_member
            else f"## {name} リーダー不在"
        )
        lines = [heading, ""]
        if membership.start_minutes is not None:
            lines.append(
                f"出撃開始: {format_clock(membership.start_minutes)}（遅れて出撃）"
            )
        lines.extend((f"所属: {len(membership.members)}人", ""))
        lines.extend(f"- {self._member_text(member)}" for member in membership.members)
        return "\n".join(lines)

    def _member_text(self, member: Member) -> str:
        """名前、VC、参加時間を書く。全時間参加のメンバーは参加時間を書かない（OUT-002）。"""

        event = self.rules.team_master.event_time
        resolved = AvailabilityResolver(event).partition([member]).confirmed
        text = member.name + ("◇" if member.has_vc else "")
        if resolved:
            availability = resolved[0]
            if (
                availability.start_minutes != event.start_minutes
                or availability.end_minutes != event.end_minutes
            ):
                text += (
                    f"（{format_clock(availability.start_minutes)}〜"
                    f"{format_clock(availability.end_minutes)}）"
                )
        return text

    @staticmethod
    def _render_supports(plan: TeamPlan) -> str:
        """出撃開始前の応援を「応援→第○隊」で描画する（FRM-042）。"""

        team_of = {
            member: membership.number
            for membership in plan.teams
            for member in membership.members
        }
        lines = [
            "## 応援",
            "",
            "| 時刻 | メンバー | 所属 | 応援 |",
            "|---|---|---|---|",
        ]
        lines.extend(
            f"| {format_clock(support.time_slot.start_minutes)} | {support.member.name} | "
            f"{team_name(team_of[support.member]) if support.member in team_of else '-'} | "
            f"応援→{team_name(support.team_number)} |"
            for support in plan.supports
        )
        return "\n".join(lines)

    @staticmethod
    def _render_notes(notes: tuple[str, ...]) -> str:
        """回答の扱いなどの注記を「注記:」の行で描画する（OUT-007）。"""

        lines = ["## 注記", ""]
        lines.extend(f"- 注記: {note}" for note in notes)
        return "\n".join(lines)

    @staticmethod
    def _render_waiting(report: ValidationReport) -> str:
        """上限のためにどの隊にも所属しないメンバーを描画する（FRM-033）。"""

        lines = [f"## 待機 {len(report.waiting)}人", ""]
        if not report.waiting:
            lines.append("なし")
        else:
            lines.extend(f"- {member.name}" for member in report.waiting)
        return "\n".join(lines)

    @staticmethod
    def _render_undecided(
        report: ValidationReport,
        undecided_leaders: dict[Member, int],
    ) -> str:
        """【別枠】参加時間未定を描画する（FRM-060）。"""

        lines = [f"## 【別枠】参加時間未定 {len(report.undecided)}人", ""]
        if not report.undecided:
            lines.append("なし")
            return "\n".join(lines)
        for member in report.undecided:
            number = undecided_leaders.get(member)
            suffix = f"（{team_name(number)}のリーダー）" if number is not None else ""
            lines.append(f"- {member.name}{suffix}")
        return "\n".join(lines)

    @staticmethod
    def _render_metrics(report: ValidationReport) -> str:
        """時間帯別の出撃人数、戦力、VC、リーダーを描画する（FRM-012）。"""

        lines = [
            "## 時間帯別の出撃",
            "",
            "| 時刻 | 隊 | 出撃人数 | 戦力 | VC | リーダー |",
            "|---|---|---:|---:|---:|---|",
        ]
        ordered = sorted(
            report.sortie_metrics,
            key=lambda metric: (metric.time_slot.start_minutes, metric.team_number),
        )
        for metric in ordered:
            clock = format_clock(metric.time_slot.start_minutes)
            name = team_name(metric.team_number)
            if not metric.started:
                lines.append(
                    f"| {clock} | {name} | - | - | - | {_leader_cell(metric)} |"
                )
                continue
            lines.append(
                f"| {clock} | {name} | {_count_cell(metric)} | "
                f"{metric.power} | {metric.vc_count} | {_leader_cell(metric)} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _render_self_check(report: ValidationReport) -> str:
        """必須条件と警告を分離した自己チェックを描画する。"""

        issue_codes = {issue.code for issue in report.issues}
        lines = [
            "## 自己チェック",
            "",
            f"- 必須条件: {'OK' if report.is_valid else 'NG'}",
            "- 所属の重複: "
            + ("NG" if ValidationCode.DUPLICATE in issue_codes else "OK"),
            "- 隊にも待機にもいない参加者: "
            + ("NG" if ValidationCode.UNASSIGNED in issue_codes else "OK"),
            f"- 待機: {len(report.waiting)}人",
            f"- 別枠: {len(report.undecided)}人",
            f"- 警告: {len(report.warnings)}件",
        ]
        if report.issues:
            lines.extend(("", "### NG詳細", ""))
            lines.extend(
                f"- {TeamPlanMarkdownExporter._issue_text(issue)}"
                for issue in report.issues
            )
        if report.warnings:
            lines.extend(("", "### 警告詳細", ""))
            lines.extend(
                f"- {TeamPlanMarkdownExporter._issue_text(warning)}"
                for warning in report.warnings
            )
        return "\n".join(lines)

    @staticmethod
    def _issue_text(issue: ValidationIssue) -> str:
        """検証結果へ対象時刻を付けて運用上の発生箇所を明示する。"""

        if issue.time_slot is None:
            return issue.message
        return f"{format_clock(issue.time_slot.start_minutes)}: {issue.message}"
