import { ItemView, WorkspaceLeaf, TFile } from "obsidian";

export const BOTTLENECK_VIEW_TYPE = "ontology-bottleneck-view";

interface BottleneckInfo {
  stage: string;
  severity: string;
  avgDays: number;
  processKey: string;
  processLabel: string;
  processFile: string;
}

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  none: 4,
};

const SEVERITY_BADGE: Record<string, string> = {
  critical: "background:#7f1d1d;color:#fca5a5;",
  high: "background:#7c2d12;color:#fdba74;",
  medium: "background:#713f12;color:#fde047;",
  low: "background:#334155;color:#94a3b8;",
};

export class BottleneckView extends ItemView {
  constructor(leaf: WorkspaceLeaf) {
    super(leaf);
  }

  getViewType(): string {
    return BOTTLENECK_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "Bottleneck Dashboard";
  }

  getIcon(): string {
    return "activity";
  }

  async onOpen() {
    await this.render();
  }

  async render() {
    const container = this.contentEl;
    container.empty();
    container.style.padding = "16px";

    container.createEl("h3", {
      text: "Process Bottlenecks",
      attr: { style: "margin-bottom:12px;font-size:16px;font-weight:700;" },
    });

    const bottlenecks = await this.loadBottlenecks();

    if (bottlenecks.length === 0) {
      container.createEl("p", {
        text: "No process files found in processes/ folder.",
        attr: { style: "color:var(--text-muted);font-size:13px;" },
      });
      return;
    }

    for (const bn of bottlenecks) {
      const card = container.createDiv({
        attr: {
          style:
            "background:var(--background-secondary);border-radius:8px;padding:12px;margin-bottom:8px;cursor:pointer;border:1px solid var(--background-modifier-border);",
        },
      });

      const header = card.createDiv({ attr: { style: "display:flex;align-items:center;gap:8px;margin-bottom:4px;" } });
      header.createEl("span", {
        text: bn.stage,
        attr: { style: "font-weight:600;font-size:13px;" },
      });
      const badgeStyle = SEVERITY_BADGE[bn.severity] || SEVERITY_BADGE.low;
      header.createEl("span", {
        text: bn.severity.toUpperCase(),
        attr: {
          style: `${badgeStyle}padding:2px 8px;border-radius:9999px;font-size:10px;font-weight:600;text-transform:uppercase;`,
        },
      });

      card.createEl("div", {
        text: `${bn.processLabel} — Avg ${bn.avgDays}d`,
        attr: { style: "font-size:11px;color:var(--text-muted);" },
      });

      card.addEventListener("click", () => {
        this.app.workspace.openLinkText(bn.processFile, "", false);
      });
    }
  }

  async loadBottlenecks(): Promise<BottleneckInfo[]> {
    const bottlenecks: BottleneckInfo[] = [];
    const files = this.app.vault.getMarkdownFiles();

    for (const file of files) {
      if (!file.path.startsWith("processes/")) continue;
      const cache = this.app.metadataCache.getFileCache(file);
      if (!cache?.frontmatter) continue;

      const fm = cache.frontmatter;
      const processKey = fm["process_id"] || "";
      const processLabel = fm["label"] || "";
      const topBottlenecks = fm["top_bottlenecks"];

      if (!Array.isArray(topBottlenecks)) continue;

      for (const bn of topBottlenecks) {
        bottlenecks.push({
          stage: bn.stage || "",
          severity: bn.severity || "none",
          avgDays: bn.avg_days || 0,
          processKey,
          processLabel,
          processFile: file.path,
        });
      }
    }

    bottlenecks.sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4));
    return bottlenecks;
  }

  async onClose() {}
}
