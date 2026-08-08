from pathlib import Path

worker_path = Path("src/adapters/chatgpt-web/browser-worker.ts")
worker = worker_path.read_text()

marker = '''  private async selectConnector(\n    page: Page,\n    captureDiagnostic?: (checkpoint: string) => Promise<void>,\n  ): Promise<Locator> {\n'''
if marker not in worker:
    raise SystemExit("selectConnector marker not found")

helper = r'''  private async selectConnectorFromToolsMenu(
    page: Page,
    composer: Locator,
    captureDiagnostic?: (checkpoint: string) => Promise<void>,
  ): Promise<Locator | undefined> {
    const composerForm = composer.locator("xpath=ancestor::form[1]");
    const triggerSelectors = [
      'button[data-testid="composer-plus-btn"]',
      'button[aria-label="Add photos & files"]',
      'button[aria-label="Add photos and files"]',
      'button[aria-label="Tools"]',
    ];
    let trigger: Locator | undefined;
    for (const selector of triggerSelectors) {
      const candidate = composerForm.locator(selector).filter({ visible: true });
      const count = await candidate.count();
      if (count > 1) {
        throw new Error(`ChatGPT composer exposed duplicate connector tools controls for ${selector}`);
      }
      if (count === 1) {
        trigger = candidate.first();
        break;
      }
    }
    if (!trigger) return undefined;

    await trigger.click();
    await captureDiagnostic?.("connector-tools-menu-triggered");
    const menuWithMore = page
      .locator('[role="menu"], [role="listbox"]')
      .filter({ visible: true })
      .filter({ has: page.getByText("More", { exact: true }) });
    try {
      await menuWithMore.first().waitFor({ state: "visible", timeout: 5_000 });
    } catch {
      await page.keyboard.press("Escape").catch(() => {});
      await captureDiagnostic?.("connector-tools-menu-missing");
      return undefined;
    }
    if (await menuWithMore.count() !== 1) {
      await page.keyboard.press("Escape").catch(() => {});
      await captureDiagnostic?.("connector-tools-menu-ambiguous");
      return undefined;
    }

    const more = menuWithMore.first().getByText("More", { exact: true }).filter({ visible: true });
    if (await more.count() !== 1) {
      await page.keyboard.press("Escape").catch(() => {});
      await captureDiagnostic?.("connector-tools-more-missing");
      return undefined;
    }
    await more.dispatchEvent("click");
    await captureDiagnostic?.("connector-tools-more-opened");

    const deadline = Date.now() + 10_000;
    while (Date.now() < deadline) {
      const appContainers = page
        .locator('[role="menu"], [role="listbox"], [role="dialog"]')
        .filter({ visible: true })
        .filter({ has: page.getByText(this.config.appName, { exact: true }) });
      const containerCount = await appContainers.count();
      if (containerCount > 0) {
        const appLabels = appContainers
          .last()
          .getByText(this.config.appName, { exact: true })
          .filter({ visible: true });
        const labelCount = await appLabels.count();
        if (labelCount === 1) {
          await appLabels.first().dispatchEvent("click");
          const selectedComposer = await this.activeComposer(page);
          const selectedConnector = this.selectedConnectorControl(selectedComposer);
          await selectedConnector.waitFor({ state: "visible", timeout: 10_000 });
          if (!await this.connectorIsSelected(selectedComposer)) {
            throw new Error(`ChatGPT tools menu did not select ${JSON.stringify(this.config.appName)} connector`);
          }
          await captureDiagnostic?.("connector-tools-app-selected");
          return selectedComposer;
        }
      }
      await new Promise(resolveSleep => setTimeout(resolveSleep, 100));
    }

    await page.keyboard.press("Escape").catch(() => {});
    await captureDiagnostic?.("connector-tools-app-missing");
    return undefined;
  }

'''
worker = worker.replace(marker, helper + marker, 1)

old_start = '''    let composer = await this.activeComposer(page);\n    await composer.fill("");\n    if (await this.connectorIsSelected(composer)) {\n      await captureDiagnostic?.("connector-already-selected");\n      return composer;\n    }\n\n    const menuRows = page.locator('.__menu-item[tabindex="0"]');\n'''
new_start = '''    let composer = await this.activeComposer(page);\n    if (await this.connectorIsSelected(composer)) {\n      await captureDiagnostic?.("connector-already-selected");\n      return composer;\n    }\n    await composer.fill("");\n\n    const toolsSelected = await this.selectConnectorFromToolsMenu(page, composer, captureDiagnostic);\n    if (toolsSelected) return toolsSelected;\n\n    // Keep @ mention as a compatibility fallback for ChatGPT surfaces that do not expose\n    // the documented + -> More app picker.\n    composer = await this.activeComposer(page);\n    await composer.fill("");\n    const menuRows = page.locator('.__menu-item[tabindex="0"]');\n'''
if old_start not in worker:
    raise SystemExit("selectConnector start block not found")
worker = worker.replace(old_start, new_start, 1)
worker_path.write_text(worker)

prompt_path = Path("src/adapters/chatgpt-web/prompt.ts")
prompt = prompt_path.read_text()
old_prompt = '''        "Preserve active instructions, decisions, completed work, unresolved work, important paths/identifiers, and any tool results needed to continue.",\n        "Return only the checkpoint summary.",\n'''
new_prompt = '''        "Preserve active instructions, decisions, completed work, unresolved work, important paths/identifiers, and any tool results needed to continue.",\n        "Keep the checkpoint concise and information-dense: use dense bullets where practical, aim for roughly 800-1,200 words, and never exceed 1,500 words.",\n        "Return only the checkpoint summary.",\n'''
if old_prompt not in prompt:
    raise SystemExit("compaction prompt block not found")
prompt = prompt.replace(old_prompt, new_prompt, 1)
prompt_path.write_text(prompt)
