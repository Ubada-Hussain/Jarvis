import React from 'react';
import { useObservability } from '../../hooks/useObservability';

export const DeveloperModePanel: React.FC = () => {
  const { runtimeState, events, isConnected } = useObservability();

  if (!runtimeState) {
    return (
      <div className="w-full fui-panel fui-border rounded flex flex-col min-h-[300px]">
        <div className="border-b border-secondary/20 px-2 py-1 bg-secondary/10 font-label-caps text-label-caps text-secondary flex justify-between">
          <span>DEV-MODE // OBSERVABILITY</span>
          <span className={isConnected ? 'text-tertiary' : 'text-error'}>
            {isConnected ? 'LIVE' : 'DISCONNECTED'}
          </span>
        </div>
        <div className="flex-grow flex items-center justify-center text-on-surface-variant/50">
          Awaiting execution state...
        </div>
      </div>
    );
  }

  return (
    <div className="w-full fui-panel fui-border rounded flex flex-col min-h-[400px] overflow-hidden">
      <div className="border-b border-secondary/20 px-2 py-1 bg-secondary/10 font-label-caps text-label-caps text-secondary flex justify-between shrink-0">
        <span>DEV-MODE // OBSERVABILITY</span>
        <span className={isConnected ? 'text-tertiary' : 'text-error'}>
          {isConnected ? 'LIVE' : 'DISCONNECTED'}
        </span>
      </div>

      <div className="flex flex-col md:flex-row flex-grow overflow-hidden">
        {/* Left column: Current State */}
        <div className="w-full md:w-1/3 border-r border-secondary/20 p-3 flex flex-col gap-3 font-mono text-xs overflow-y-auto shrink-0">
          <div className="text-primary font-bold mb-1 border-b border-primary/20 pb-1">RUNTIME STATE</div>
          
          <div className="flex justify-between items-center">
            <span className="text-secondary/70">STATUS:</span>
            <span className={`px-2 py-0.5 rounded ${
              runtimeState.status === 'FAILED' ? 'bg-error/20 text-error' :
              runtimeState.status === 'COMPLETED' ? 'bg-tertiary/20 text-tertiary' :
              runtimeState.status === 'IDLE' ? 'bg-surface-container-high' :
              'bg-primary/20 text-primary animate-pulse'
            }`}>
              {runtimeState.status}
            </span>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-secondary/70">TASK ID:</span>
            <span className="text-on-surface truncate" title={runtimeState.task_id || 'N/A'}>
              {runtimeState.task_id || 'N/A'}
            </span>
          </div>
          
          <div className="flex flex-col gap-1">
            <span className="text-secondary/70">AGENT:</span>
            <span className="text-on-surface">{runtimeState.active_agent || 'None'}</span>
          </div>
          
          <div className="flex flex-col gap-1">
            <span className="text-secondary/70">TOOL:</span>
            <span className="text-on-surface text-tertiary">{runtimeState.active_tool || 'None'}</span>
          </div>
          
          <div className="flex flex-col gap-1">
            <span className="text-secondary/70">MODEL:</span>
            <span className="text-on-surface">{runtimeState.model || 'N/A'}</span>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-secondary/70">ELAPSED:</span>
            <span className="text-on-surface">{runtimeState.elapsed_time} ms</span>
          </div>

          {runtimeState.last_error && (
            <div className="flex flex-col gap-1 mt-2 p-2 bg-error/10 border border-error/30 rounded">
              <span className="text-error font-bold">ERROR:</span>
              <span className="text-error break-words whitespace-pre-wrap">{runtimeState.last_error}</span>
            </div>
          )}

          {runtimeState.task_graph && (
            <div className="mt-4 border-t border-primary/20 pt-2 flex flex-col gap-2">
              <div className="text-primary font-bold">TASK GRAPH</div>
              <div className="text-[10px] text-secondary/70 uppercase mb-1">
                {runtimeState.task_graph.objective}
              </div>
              <div className="flex flex-col gap-2">
                {Object.values(runtimeState.task_graph.nodes).map((node: any) => (
                  <div key={node.node_id} className="bg-surface-container p-2 rounded border border-secondary/20 flex flex-col gap-1">
                    <div className="flex justify-between items-start">
                      <span className="font-bold text-on-surface text-[10px]">{node.agent}</span>
                      <span className={`text-[9px] px-1 rounded ${
                        node.status === 'COMPLETED' ? 'bg-tertiary/20 text-tertiary' :
                        node.status === 'FAILED' || node.status === 'BLOCKED' ? 'bg-error/20 text-error' :
                        node.status === 'RUNNING' ? 'bg-primary/20 text-primary animate-pulse' :
                        'bg-surface-container-highest text-secondary/70'
                      }`}>
                        {node.status}
                      </span>
                    </div>
                    <span className="text-on-surface-variant text-[10px] truncate" title={node.description}>
                      {node.description}
                    </span>
                    {node.dependencies?.length > 0 && (
                      <span className="text-secondary/50 text-[9px]">Deps: {node.dependencies.join(', ')}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right column: Event Timeline */}
        <div className="w-full md:w-2/3 p-3 flex flex-col gap-2 font-mono text-xs overflow-y-auto bg-surface-container-lowest/30">
          <div className="text-primary font-bold mb-1 sticky top-0 bg-background/90 backdrop-blur pb-1 z-10 border-b border-primary/20">
            EVENT TIMELINE
          </div>
          
          {events.length === 0 ? (
            <div className="text-on-surface-variant/40 italic">No events recorded.</div>
          ) : (
            <div className="flex flex-col gap-2">
              {events.map((ev, idx) => (
                <div key={ev.event_id || idx} className="border-l-2 border-primary/40 pl-2 py-1 flex flex-col gap-1 bg-surface-container-low/30 rounded-r">
                  <div className="flex justify-between items-start">
                    <span className="font-bold text-secondary">{ev.event_type}</span>
                    <span className="text-on-surface-variant/50 text-[10px]">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-on-surface/80">
                    {ev.agent && <span>Agent: <span className="text-primary">{ev.agent}</span></span>}
                    {ev.tool && <span>Tool: <span className="text-tertiary">{ev.tool}</span></span>}
                    {ev.status && (
                      <span>Status: <span className={
                        ev.status === 'DENIED' || ev.status === 'FAILED' ? 'text-error' : 
                        ev.status === 'EXECUTED' || ev.status === 'COMPLETED' ? 'text-tertiary' : 'text-primary'
                      }>{ev.status}</span></span>
                    )}
                    {ev.duration_ms !== null && <span>Took: {ev.duration_ms}ms</span>}
                    {ev.risk_level && <span>Risk: {ev.risk_level}</span>}
                    {ev.verification_status && <span>Verify: {ev.verification_status}</span>}
                  </div>
                  
                  {ev.error && (
                    <div className="text-error mt-1 bg-error/10 p-1 rounded break-words">
                      {ev.error}
                    </div>
                  )}

                  {ev.metadata && Object.keys(ev.metadata).length > 0 && (
                    <div className="mt-1 text-on-surface-variant/70 bg-black/20 p-1 rounded overflow-x-auto whitespace-pre">
                      {JSON.stringify(ev.metadata, null, 2)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
