import { Plugin, MarkdownPostProcessorContext } from "obsidian";
import cytoscape from "cytoscape";
import dagre from "cytoscape-dagre";

cytoscape.use(dagre);

interface StageData {
  stage_key: string;
  name: string;
  order: number;
  type: string;
  severity: string;
  avg_days: number;
  p90_days: number;
  sla_target_days: number;
  sla_met_pct: number;
  error_rate: number;
  entry_count: number;
  exit_count: number;
  predecessors: string[];
  successors: string[];
  entities: string[];
}

interface ProcessEntry {
  label: string;
  file: string;
  total_stages: number;
  total_cycle_time_days: number;
  throughput_per_month: number;
  top_bottleneck_severity: string;
  bottleneck_stages: string[];
  entity_participation: Record<string, string[]>;
  stages: StageData[];
}

interface ProcessIndex {
  [key: string]: ProcessEntry;
}

const SEVERITY_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  critical: { bg: "#7f1d1d", border: "#ef4444", text: "#fca5a5" },
  high: { bg: "#7c2d12", border: "#f97316", text: "#fdba74" },
  medium: { bg: "#713f12", border: "#eab308", text: "#fde68a" },
  low: { bg: "#1e293b", border: "#475569", text: "#94a3b8" },
  none: { bg: "#14532d", border: "#22c55e", text: "#86efac" },
};

function parseConfig(source: string): Record<string, string> {
  const config: Record<string, string> = {};
  for (const line of source.split("\n")) {
    const match = line.match(/^(\w+):\s*(.+)$/);
    if (match) config[match[1]] = match[2].trim();
  }
  return config;
}

async function loadProcessIndex(plugin: Plugin): Promise<ProcessIndex | null> {
  const file = plugin.app.vault.getAbstractFileByPath("_meta/process_index.json");
  if (!file) return null;
  const content = await plugin.app.vault.cachedRead(file as any);
  return JSON.parse(content);
}

function renderProcessFlow(
  container: HTMLElement,
  stages: StageData[],
  plugin: Plugin,
  processFile: string,
) {
  container.style.width = "100%";
  container.style.height = "500px";
  container.style.borderRadius = "8px";
  container.style.border = "1px solid var(--background-modifier-border)";
  container.style.marginBottom = "16px";

  const elements: cytoscape.ElementDefinition[] = [];

  for (const stage of stages) {
    const sev = SEVERITY_COLORS[stage.severity] || SEVERITY_COLORS.none;
    const typeLabel =
      stage.type === "parallel" ? "\n(support)" :
      stage.type === "post_close" ? "\n(post-close)" : "";

    elements.push({
      group: "nodes",
      data: {
        id: stage.stage_key,
        label: `${stage.name}${typeLabel}\n${stage.avg_days}d avg`,
        severity: stage.severity,
        type: stage.type,
        avgDays: stage.avg_days,
        p90Days: stage.p90_days,
        slaTarget: stage.sla_target_days,
        slaMet: stage.sla_met_pct,
        errorRate: stage.error_rate,
        entryCount: stage.entry_count,
        exitCount: stage.exit_count,
        bgColor: sev.bg,
        borderColor: sev.border,
        textColor: sev.text,
      },
    });
  }

  for (const stage of stages) {
    for (const succKey of stage.successors) {
      const target = stages.find((s) => s.stage_key === succKey);
      if (target) {
        elements.push({
          group: "edges",
          data: {
            id: `${stage.stage_key}-${succKey}`,
            source: stage.stage_key,
            target: succKey,
            volume: stage.exit_count,
            edgeType: stage.type === "parallel" ? "parallel" : "sequential",
          },
        });
      }
    }
  }

  const cy = cytoscape({
    container,
    elements,
    style: [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "text-valign": "center",
          "text-halign": "center",
          "font-size": "9px",
          "font-weight": "bold" as any,
          color: "#e2e8f0",
          "text-wrap": "wrap" as any,
          "text-max-width": "110px",
          width: 140,
          height: 52,
          shape: "roundrectangle",
          "background-color": "data(bgColor)",
          "border-width": 3,
          "border-color": "data(borderColor)",
        },
      },
      {
        selector: 'node[type="parallel"]',
        style: {
          "border-style": "dashed" as any,
          width: 120,
          height: 44,
          "font-size": "8px",
        },
      },
      {
        selector: 'node[type="post_close"]',
        style: {
          "border-style": "dotted" as any,
          "background-color": "#0f172a",
          color: "#94a3b8",
          "font-size": "8px",
          width: 120,
          height: 44,
        },
      },
      {
        selector: "node:selected",
        style: { "border-color": "#60a5fa", "border-width": 4 },
      },
      {
        selector: "edge",
        style: {
          width: 2,
          "line-color": "#475569",
          "target-arrow-color": "#64748b",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          label: "data(volume)",
          "font-size": "8px",
          color: "#94a3b8",
          "text-background-color": "#0f172a",
          "text-background-opacity": 0.8,
          "text-background-padding": "2px" as any,
          "arrow-scale": 0.8,
        },
      },
      {
        selector: 'edge[edgeType="parallel"]',
        style: {
          "line-style": "dashed",
          "line-dash-pattern": [6, 3] as any,
          "line-color": "#6d28d9",
          "target-arrow-color": "#6d28d9",
        },
      },
    ],
    layout: {
      name: "dagre",
      rankDir: "LR",
      nodeSep: 40,
      rankSep: 80,
      padding: 30,
    } as any,
    minZoom: 0.3,
    maxZoom: 3,
    wheelSensitivity: 0.3,
  });

  // Legend
  const legend = document.createElement("div");
  legend.style.cssText =
    "display:flex;gap:16px;padding:8px 12px;font-size:11px;color:#94a3b8;flex-wrap:wrap;align-items:center;";
  legend.innerHTML = [
    '<span style="display:inline-flex;align-items:center;gap:4px"><span style="width:12px;height:12px;background:#7f1d1d;border:2px solid #ef4444;border-radius:2px;display:inline-block"></span> Critical</span>',
    '<span style="display:inline-flex;align-items:center;gap:4px"><span style="width:12px;height:12px;background:#7c2d12;border:2px solid #f97316;border-radius:2px;display:inline-block"></span> High</span>',
    '<span style="display:inline-flex;align-items:center;gap:4px"><span style="width:12px;height:12px;background:#14532d;border:2px solid #22c55e;border-radius:2px;display:inline-block"></span> On Track</span>',
    '<span style="display:inline-flex;align-items:center;gap:4px"><span style="width:12px;height:12px;border:2px dashed #6d28d9;border-radius:2px;display:inline-block"></span> Support</span>',
    '<span style="display:inline-flex;align-items:center;gap:4px"><span style="width:12px;height:12px;border:2px dotted #475569;background:#0f172a;border-radius:2px;display:inline-block"></span> Post-Close</span>',
    '<span style="color:#64748b">| Numbers on arrows = loan volume</span>',
  ].join("");
  container.parentElement?.insertBefore(legend, container.nextSibling);

  // Click node → scroll to stage section
  cy.on("tap", "node", (evt) => {
    const nodeData = evt.target.data();
    const stage = stages.find((s) => s.stage_key === nodeData.id);
    if (!stage) return;

    const file = plugin.app.vault.getAbstractFileByPath(processFile);
    if (file) {
      plugin.app.workspace.openLinkText(processFile, "", false);
      setTimeout(() => {
        const leaf = plugin.app.workspace.getActiveViewOfType(null as any);
        if (leaf) {
          const editor = (leaf as any).editor;
          if (editor) {
            const content = editor.getValue();
            const idx = content.indexOf(`### Stage ${stage.order}: ${stage.name}`);
            if (idx >= 0) {
              const line = content.substring(0, idx).split("\n").length - 1;
              editor.setCursor({ line, ch: 0 });
              editor.scrollIntoView(
                { from: { line, ch: 0 }, to: { line: line + 1, ch: 0 } },
                true,
              );
            }
          }
        }
      }, 300);
    }
  });

  // Tooltip on hover
  const tooltip = document.createElement("div");
  tooltip.style.cssText =
    "position:absolute;background:#1e293b;color:#e2e8f0;padding:8px 12px;border-radius:6px;font-size:11px;pointer-events:none;z-index:999;display:none;border:1px solid #334155;max-width:220px;line-height:1.5;";
  container.style.position = "relative";
  container.appendChild(tooltip);

  cy.on("mouseover", "node", (evt) => {
    const d = evt.target.data();
    const stage = stages.find((s) => s.stage_key === d.id);
    if (!stage) return;
    const sevLabel = stage.severity === "none" ? "on track" : stage.severity;
    tooltip.innerHTML = [
      `<strong>${stage.name}</strong> <span style="color:${(SEVERITY_COLORS[stage.severity] || SEVERITY_COLORS.none).border}">(${sevLabel})</span>`,
      `Avg: ${stage.avg_days}d &nbsp;|&nbsp; P90: ${stage.p90_days}d`,
      `SLA: ${stage.sla_target_days}d &nbsp;|&nbsp; Met: ${stage.sla_met_pct}%`,
      `Error: ${stage.error_rate}% &nbsp;|&nbsp; Vol: ${stage.entry_count.toLocaleString()} → ${stage.exit_count.toLocaleString()}`,
    ].join("<br>");
    tooltip.style.display = "block";
    const pos = evt.target.renderedPosition();
    tooltip.style.left = `${pos.x + 10}px`;
    tooltip.style.top = `${pos.y - 80}px`;
  });

  cy.on("mouseout", "node", () => {
    tooltip.style.display = "none";
  });
}

export function registerProcessFlowBlock(plugin: Plugin) {
  plugin.registerMarkdownCodeBlockProcessor(
    "ontology-flow",
    async (source: string, el: HTMLElement, ctx: MarkdownPostProcessorContext) => {
      const config = parseConfig(source);
      const processKey = config["process"] || "loan-origination";

      const index = await loadProcessIndex(plugin);
      if (!index || !index[processKey]) {
        el.createEl("p", {
          text: `Process not found: ${processKey}. Check _meta/process_index.json`,
          cls: "mod-warning",
        });
        return;
      }

      const processEntry = index[processKey];
      if (!processEntry.stages || processEntry.stages.length === 0) {
        el.createEl("p", {
          text: "No stage data in process_index.json.",
          cls: "mod-warning",
        });
        return;
      }

      const container = el.createDiv();
      renderProcessFlow(container, processEntry.stages, plugin, processEntry.file);
    },
  );
}
