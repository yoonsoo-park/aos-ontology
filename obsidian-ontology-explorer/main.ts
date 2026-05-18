import { Plugin } from "obsidian";
import { registerProcessFlowBlock } from "./src/process-flow";
import { BottleneckView, BOTTLENECK_VIEW_TYPE } from "./src/bottleneck-view";

export default class OntologyExplorerPlugin extends Plugin {
  async onload() {
    registerProcessFlowBlock(this);

    this.registerView(BOTTLENECK_VIEW_TYPE, (leaf) => new BottleneckView(leaf));

    this.addRibbonIcon("activity", "Bottleneck Dashboard", () => {
      this.activateBottleneckView();
    });

    this.addCommand({
      id: "open-bottleneck-dashboard",
      name: "Open Bottleneck Dashboard",
      callback: () => this.activateBottleneckView(),
    });
  }

  async activateBottleneckView() {
    const { workspace } = this.app;
    let leaf = workspace.getLeavesOfType(BOTTLENECK_VIEW_TYPE)[0];
    if (!leaf) {
      const rightLeaf = workspace.getRightLeaf(false);
      if (rightLeaf) {
        await rightLeaf.setViewState({ type: BOTTLENECK_VIEW_TYPE, active: true });
        leaf = rightLeaf;
      }
    }
    if (leaf) workspace.revealLeaf(leaf);
  }

  onunload() {}
}
