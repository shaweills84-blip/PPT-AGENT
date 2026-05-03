import json
from agent.sub_agents.research_agent import ResearchAgent
from agent.sub_agents.outline_agent import OutlineAgent


class PPTOrchestrator:
    """PPT 生成总调度。对话澄清意图 → 确认结构 → Orchestrator 接手生成。

    流程: ResearchAgent 检索 → 质量评估 → OutlineAgent 规划 → 质量评估 → 输出
    """

    def __init__(self):
        self.research_agent = ResearchAgent()
        self.outline_agent = OutlineAgent()

    def run(self, context: dict, document_id: int,
            strategy: str = "basic",
            enable_web_search: bool = False,
            max_retries: int = 2) -> dict:
        workflow_log = []

        research_prompt = self._build_research_prompt(context)

        # Stage 1: 研究
        workflow_log.append("Orchestrator → Research Agent: 开始研究")
        research_report = None

        for attempt in range(max_retries):
            research_report = self.research_agent.research(
                prompt=research_prompt,
                document_id=document_id,
                strategy=strategy,
                enable_web_search=enable_web_search,
                retrieval_cache=context.get("retrieval_cache", {}),
            )

            quality = self._assess_research_quality(research_report, research_prompt)
            workflow_log.append(f"研究质量评估: {quality}")

            if quality["sufficient"]:
                break
            else:
                if attempt < max_retries - 1:
                    workflow_log.append(
                        f"研究不充分 ({quality['issues']})，重新研究"
                    )
                    feedback = f"你上次的研究缺少: {quality['issues']}。请针对这些缺口重新检索文档，补充研究报告。"
                    research_prompt = f"{research_prompt}\n\n【补充要求】{feedback}"
                else:
                    workflow_log.append("研究达到最大重试次数，使用当前报告继续")

        # Stage 2: 大纲规划
        workflow_log.append("Orchestrator → Outline Agent: 开始规划大纲")

        template_style = context.get("preferences", "")
        user_prompt = self._build_user_prompt(context)

        slides = None
        for attempt in range(max_retries):
            slides = self.outline_agent.plan(
                research_report=research_report,
                user_prompt=user_prompt,
                template_style=template_style,
            )

            quality = self._assess_outline_quality(slides)
            workflow_log.append(f"大纲质量评估: {quality}")

            if quality["acceptable"]:
                break
            else:
                if attempt < max_retries - 1:
                    workflow_log.append(
                        f"大纲不理想 ({quality['issues']})，要求修改"
                    )
                    slides = self.outline_agent.revise(
                        current_slides=slides,
                        feedback=quality["issues"],
                        research_report=research_report,
                    )
                else:
                    workflow_log.append("大纲达到最大重试次数，使用当前版本")

        return {
            "success": slides is not None and bool(slides.get("slides", [])),
            "slides": slides or {"title": "生成失败", "slides": []},
            "research_report": research_report,
            "workflow_log": workflow_log,
        }

    def _build_research_prompt(self, context: dict) -> str:
        clarified = context.get("clarified", {})

        parts = []

        topic = clarified.get("topic", "")
        if topic:
            parts.append(f"PPT 主题：{topic}")

        focus = clarified.get("focus", "")
        if focus:
            parts.append(f"侧重点：{focus}")

        style = clarified.get("style", "")
        if style:
            parts.append(f"风格要求：{style}")

        structure = clarified.get("structure", [])
        if structure:
            parts.append(f"期望结构：{' → '.join(structure)}")

        if not parts and context.get("messages"):
            recent_user_msgs = [
                m["content"] for m in context["messages"]
                if m.get("role") == "user"
            ][-3:]
            if recent_user_msgs:
                parts.append(f"用户需求：{' '.join(recent_user_msgs)}")

        if not parts:
            parts.append("请根据文档内容生成 PPT")

        return "\n".join(parts)

    def _build_user_prompt(self, context: dict) -> str:
        clarified = context.get("clarified", {})
        topic = clarified.get("topic", "文档内容")
        focus = clarified.get("focus", "")
        if focus:
            return f"关于「{topic}」的 PPT，侧重点：{focus}"
        return f"关于「{topic}」的 PPT"

    def _assess_research_quality(self, report: dict, prompt: str) -> dict:
        issues = []

        if not report:
            return {"sufficient": False, "issues": "研究报告为空"}

        key_findings = report.get("key_findings", [])
        if not key_findings:
            issues.append("缺少核心发现")
        elif len(key_findings) < 3:
            issues.append(f"核心发现不足（仅{len(key_findings)}条）")

        dimensions = report.get("dimensions", [])
        if not dimensions:
            issues.append("缺少维度分析")
        elif len(dimensions) < 2:
            issues.append(f"分析维度不足（仅{len(dimensions)}个）")

        gaps = report.get("knowledge_gaps", [])
        if gaps and len(gaps) > 3:
            issues.append(f"信息缺口过多（{len(gaps)}个）")

        return {
            "sufficient": len(issues) == 0,
            "issues": "; ".join(issues) if issues else "研究充分",
        }

    def _assess_outline_quality(self, slides: dict) -> dict:
        issues = []

        if not slides:
            return {"acceptable": False, "issues": "大纲为空"}

        slide_list = slides.get("slides", [])
        if not slide_list:
            return {"acceptable": False, "issues": "幻灯片列表为空"}

        if len(slide_list) < 4:
            issues.append(f"幻灯片数量过少（{len(slide_list)}张）")
        elif len(slide_list) > 15:
            issues.append(f"幻灯片数量过多（{len(slide_list)}张）")

        has_title = any(s.get("type") == "title" for s in slide_list)
        if not has_title:
            issues.append("缺少封面页（type: title）")

        has_summary = any(s.get("type") == "summary" for s in slide_list)
        if not has_summary:
            issues.append("缺少总结页（type: summary）")

        placeholder_patterns = ["描述1", "要点1", "内容A", "占位符", "TBD", "TODO"]
        for s in slide_list:
            for key in ("title", "bullets", "key_points"):
                text = json.dumps(s.get(key, ""), ensure_ascii=False)
                for pat in placeholder_patterns:
                    if pat in text:
                        issues.append(f"存在占位符「{pat}」")
                        break

        return {
            "acceptable": len(issues) == 0,
            "issues": "; ".join(issues) if issues else "大纲质量合格",
        }
