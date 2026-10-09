import { useEffect, useRef, useState } from "react";
import cytoscape, { Core } from "cytoscape";
import { api, Fact, Graph, GraphEdge, GraphNode, label } from "./api";

export default function GraphView({
  active,
  revision,
  onEvidence,
  report,
}: {
  active: boolean;
  revision: number;
  onEvidence: (fact: Fact) => void;
  report: (error: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null),
    cy = useRef<Core | null>(null);
  const [graph, setGraph] = useState<Graph>({ nodes: [], edges: [] }),
    [selected, setSelected] = useState<GraphNode | null>(null),
    [edge, setEdge] = useState<GraphEdge | null>(null);
  const [caseRef, setCaseRef] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [proposed, setProposed] = useState(false);
  const [pathFrom, setPathFrom] = useState(""),
    [pathTo, setPathTo] = useState(""),
    [pathMessage, setPathMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const requestKey = `case=${encodeURIComponent(caseRef)}&date_from=${from}&date_to=${to}&proposed=${proposed}`;
  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    api<Graph>("/graph?" + requestKey)
      .then((g) => {
        if (!cancelled) setGraph(g);
      })
      .catch((e) => report(e.message))
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [revision, requestKey, report]);
  useEffect(() => {
    if (!container.current || !active) return;
    cy.current = cytoscape({
      container: container.current,
      elements: [
        ...graph.nodes.map((n) => ({ data: { ...n, type: n.type } })),
        ...graph.edges.map((e) => ({ data: e })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#66ceb7",
            label: "data(label)",
            "font-size": 11,
            color: "#d5e3e8",
            "text-valign": "bottom",
            "text-margin-y": 10,
            width: 26,
            height: 26,
            "border-width": 5,
            "border-color": "#163d3c",
            "text-wrap": "wrap",
            "text-max-width": "130px",
          },
        },
        {
          selector: 'node[type="Person"]',
          style: {
            width: 38,
            height: 38,
            "background-color": "#9adfce",
            "border-color": "#22584e",
          },
        },
        {
          selector: 'node[type="Document"]',
          style: {
            shape: "round-rectangle",
            "background-color": "#71899a",
            "border-color": "#243d51",
          },
        },
        {
          selector: 'node[type="Mention"]',
          style: { "background-color": "#e1b980", "border-color": "#5c4b38" },
        },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": "#355b60",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#355b60",
            "arrow-scale": 0.6,
          },
        },
        {
          selector: 'edge[status="proposed"]',
          style: { "line-style": "dashed", "line-color": "#bd9560" },
        },
        {
          selector: ".path",
          style: {
            "line-color": "#f0cc88",
            "background-color": "#f0cc88",
            width: 4,
          },
        },
        {
          selector: ":selected",
          style: { "border-color": "#fff", "border-width": 3 },
        },
      ],
      layout: { name: "preset" },
      wheelSensitivity: 0.25,
    });
    const instance = cy.current;
    const layout = instance.layout({
      name: "cose",
      animate: false,
      fit: true,
      padding: 45,
      nodeRepulsion: () => 12000,
    });
    layout.run();
    cy.current.on("tap", "node", (event) => {
      setSelected(event.target.data());
      setEdge(null);
    });
    cy.current.on("tap", "edge", (event) => {
      setEdge(event.target.data());
      setSelected(null);
    });
    return () => {
      layout.stop();
      instance.stop(true, false);
      instance.destroy();
      if (cy.current === instance) cy.current = null;
    };
  }, [graph, active]);
  async function expand() {
    if (!selected) return;
    setBusy(true);
    try {
      const added = await api<Graph>(
        "/graph/neighbors/" + encodeURIComponent(selected.id) + "?limit=30",
      );
      setGraph((g) => ({
        nodes: [
          ...new Map(
            [...g.nodes, ...added.nodes].map((n) => [n.id, n]),
          ).values(),
        ],
        edges: [
          ...new Map(
            [...g.edges, ...added.edges].map((e) => [e.id, e]),
          ).values(),
        ],
      }));
    } catch (e) {
      report((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function trace() {
    setBusy(true);
    try {
      const path = await api<{ nodes: string[]; edges: GraphEdge[] }>(
        "/graph/path?source=" +
          encodeURIComponent(pathFrom) +
          "&target=" +
          encodeURIComponent(pathTo) +
          "&" +
          requestKey,
      );
      cy.current?.elements().removeClass("path");
      for (const id of [...path.nodes, ...path.edges.map((e) => e.id)])
        cy.current?.getElementById(id).addClass("path");
      setPathMessage(
        path.nodes.length
          ? `Path found across ${path.edges.length} sourced relationships.`
          : "No path exists within 6 hops and these filters.",
      );
    } catch (e) {
      report((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="graph-view">
      <div className="filters">
        <label>
          Case Reference
          <input
            name="graph-case"
            autoComplete="off"
            placeholder="SYN-CASE-01…"
            value={caseRef}
            onChange={(e) => setCaseRef(e.target.value)}
          />
        </label>
        <label>
          From
          <input
            name="graph-from"
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label>
          To
          <input
            name="graph-to"
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={proposed}
            onChange={(e) => setProposed(e.target.checked)}
          />
          Include Proposed
        </label>
      </div>
      <div className="graph-layout">
        <div className="graph-canvas">
          <div
            ref={container}
            className="network"
            role="img"
            aria-label={`Knowledge graph with ${graph.nodes.length} nodes. Use the entity list below for keyboard navigation.`}
          />
          {!graph.nodes.length && !busy && (
            <div className="graph-empty">
              No Relationships Yet
              <span>Commit supported records to build the graph.</span>
            </div>
          )}
          <div className="graph-tools">
            <button onClick={() => cy.current?.zoom(cy.current.zoom() * 1.2)}>
              Zoom In
            </button>
            <button onClick={() => cy.current?.zoom(cy.current.zoom() / 1.2)}>
              Zoom Out
            </button>
            <button onClick={() => cy.current?.fit(undefined, 40)}>
              Fit Graph
            </button>
          </div>
          <div className="graph-caption">
            SOLID: SUPPORTED · DASHED: PROPOSED
          </div>
        </div>
        <aside className="panel graph-inspector">
          <div className="eyebrow">Relationship Inspector</div>
          {selected ? (
            <>
              <h3>{selected.label}</h3>
              <span className="badge">{selected.type}</span>
              <p>
                Expand up to 30 immediate neighbours. A connection does not
                establish guilt.
              </p>
              <button className="primary" onClick={expand} disabled={busy}>
                Expand Neighbours
              </button>
            </>
          ) : edge ? (
            <>
              <h3>{label(edge.label)}</h3>
              <span className="badge">{label(edge.status)}</span>
              <p>{edge.evidence.length} supporting claims</p>
              {edge.evidence.map((id) => (
                <button
                  className="source-link"
                  key={id}
                  onClick={() =>
                    api<Fact>("/evidence/" + id)
                      .then(onEvidence)
                      .catch((e) => report(e.message))
                  }
                >
                  Inspect {id.slice(-8)} ↗
                </button>
              ))}
            </>
          ) : (
            <>
              <h3>Every Connection Has a Source</h3>
              <p>
                Select a node or relationship, or use the accessible list below.
              </p>
            </>
          )}
          <hr />
          <h3>Trace a Path</h3>
          <label>
            From Entity
            <select
              name="path-from"
              value={pathFrom}
              onChange={(e) => setPathFrom(e.target.value)}
            >
              <option value="">Select Entity</option>
              {graph.nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            To Entity
            <select
              name="path-to"
              value={pathTo}
              onChange={(e) => setPathTo(e.target.value)}
            >
              <option value="">Select Entity</option>
              {graph.nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.label}
                </option>
              ))}
            </select>
          </label>
          <button onClick={trace} disabled={!pathFrom || !pathTo || busy}>
            Find Shortest Path
          </button>
          <p aria-live="polite">{busy ? "Loading Graph…" : pathMessage}</p>
        </aside>
      </div>
      {graph.truncated && (
        <p className="notice">
          Graph capped at 200 nodes. Narrow the case or date filters to explore
          additional records.
        </p>
      )}
      <details className="panel">
        <summary>
          Keyboard Entity & Relationship List ({graph.nodes.length})
        </summary>
        <div className="node-list">
          {graph.nodes.map((n) => (
            <button
              key={n.id}
              onClick={() => {
                setSelected(n);
                setEdge(null);
                cy.current?.center(cy.current.getElementById(n.id));
              }}
            >
              {n.label}
              <span>{n.type}</span>
            </button>
          ))}
        </div>
        <div className="node-list">
          {graph.edges.map((e) => (
            <button
              key={e.id}
              onClick={() => {
                setEdge(e);
                setSelected(null);
              }}
            >
              {label(e.label)}
              <span>{e.evidence.length} claims</span>
            </button>
          ))}
        </div>
      </details>
    </section>
  );
}
