import { useEffect, useState } from 'react';
import type { DocRouterOrgApi } from '@/utils/api';

/** Loads all org flow ids → display names (paginated). Used for canvas subtitles. */
export function useOrgFlowNameMap(flowOrgApi: DocRouterOrgApi | null | undefined): Record<string, string> {
  const [flowNameById, setFlowNameById] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!flowOrgApi) {
      setFlowNameById({});
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const map: Record<string, string> = {};
        let offset = 0;
        const limit = 200;
        for (;;) {
          const res = await flowOrgApi.listFlows({ limit, offset });
          for (const row of res.items) {
            const fid = row.flow?.flow_id ?? '';
            if (!fid) continue;
            map[fid] = row.flow?.name?.trim() || fid;
          }
          offset += res.items.length;
          if (res.items.length === 0 || offset >= res.total) break;
        }
        if (!cancelled) setFlowNameById(map);
      } catch {
        if (!cancelled) setFlowNameById({});
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [flowOrgApi]);

  return flowNameById;
}
