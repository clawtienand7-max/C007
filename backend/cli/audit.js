// CLI: run the UI Audit Agent and print the report. `npm run audit`.
import { audit } from "../agents/uiAudit.js";

const report = audit();
console.log(JSON.stringify(report, null, 2));
console.log(
  `\nSummary: ${report.connected}/${report.total_elements} connected, ${report.fake_or_incomplete} incomplete.`,
);
process.exit(report.fake_or_incomplete === 0 ? 0 : 1);
