# 2026-07-20 今日投递清单

## 通用简历

统一使用这份，不再按公司切换版本：

- [通用简历 PDF](<generic_resume/resume.pdf>)
- [通用简历 Markdown](<generic_resume/source/Yang_Yu_Generic_Software_Engineer_Resume.md>)
- [ATS 审计](<generic_resume/reports/Yang_Yu_Generic_Software_Engineer_ATS_Report.md>)

SpeedyApply 上游截至今天没有 `0d` 岗位；最新一批为 `1d`，共四条。Google Technical Program Manager I 因岗位族不是 SWE/AI/Data 已排除。以下三条均已抓取 JD，并生成独立的一页英文 PDF。

## 1. Deepgram - Software Engineering Internship

- 建议：立即投递，三者中匹配度最高
- 地点：Remote, USA
- Cohort：优先选择 Summer 2027
- 申请：https://jobs.ashbyhq.com/deepgram/dc8693b5-72ce-4ca3-ab15-9c8434d35da1
- 简历：`deepgram_software-engineering-intern/resume.pdf`
- 主要匹配：AI-first/agentic workflow、项目构建、调试、测试、分布式系统、在读 CS 硕士
- 主要缺口：没有语音/音频、ASR/TTS 证据；这些词没有硬塞进简历

## 2. WonderBotz - Junior Software Engineer

- 建议：确认时间和身份问题后投递
- 地点：Princeton, NJ，on-site
- 申请：http://wonderbotz.applytojob.com/apply/RrI9QanYDY/Junior-Software-Engineer
- 简历：`wonderbotz_junior-software-engineer/resume.pdf`
- 主要匹配：Python、SQL、APIs、AI/ML、自动化工作流、排错和测试
- 提交前必须本人回答：最早入职日期、是否在美国、是否需要 sponsorship、是否愿意搬到 Princeton
- 主要缺口：没有 UiPath/Automation Anywhere/Blue Prism 或 RPA 行业经验

## 3. Esri - Software Engineer I, Front-End

- 建议：第三顺位，属于 stretch application
- 地点：Redlands, CA
- 申请：https://www.esri.com/careers/5190253007?gh_jid=5190253007
- 简历：`esri_software-engineer-i-front-end/resume.pdf`
- 主要匹配：JavaScript、REST APIs、Python/Java、Git、RAG/embeddings、用户侧搜索推荐项目
- 主要缺口：没有可验证的 React/TypeScript/HTML/CSS、WCAG/ARIA 或 GIS 经历

## 文件说明

每个岗位目录包含：

- `resume.pdf`：直接上传表单的一页英文简历
- `resume.tex`：可继续修改并重新编译的源文件
- `source/Yang_Yu_*_Resume.md`：ATS 纯文本权威副本
- `reports/Yang_Yu_*_ATS_Report.md`：关键词覆盖、缺口和真实性审计
- `build/resume.aux|log|out`：LaTeX 编译中间文件
- `job.md`：JD 摘要、申请链接和表单提醒
- `metadata.json`：岗位与验证状态
- `preview.png`：PDF 版面预览

三份 PDF 均通过：一页、LaTeX 无警告、文字可抽取、无图片/多栏/文本框。
