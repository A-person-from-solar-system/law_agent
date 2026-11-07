import type { RunStatus } from "@/lib/contracts";
import { statusLabel } from "@/lib/format";
export function StatusBadge({ status }: { status: RunStatus }) { return <span className={`status status-${status}`}><i />{statusLabel[status]}</span>; }
