/**
 * Hermes Workflow — Dashboard Plugin
 *
 * Visualize, edit and review the pipeline workflows (workflows/*.yaml) as a
 * Step Functions-style graph: directed arrows between states, explicit
 * pass/fail branches on gates, collapsible parallel boxes, a live-validated
 * YAML editor, a property side-panel, edge reconnection, a 3-step onboarding
 * overlay, and a review diff of unsaved changes.
 *
 * Plain IIFE, no build step. Uses window.__HERMES_PLUGIN_SDK__ for React +
 * shadcn primitives. Backend at /api/plugins/workflow/.
 */
(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;

  var React = SDK.React;
  var h = React.createElement;
  var hooks = SDK.hooks;
  var useState = hooks.useState;
  var useEffect = hooks.useEffect;
  var useCallback = hooks.useCallback;
  var useMemo = hooks.useMemo;
  var useRef = hooks.useRef;

  var C = SDK.components;
  var Card = C.Card, CardHeader = C.CardHeader, CardTitle = C.CardTitle,
      CardContent = C.CardContent, Badge = C.Badge, Button = C.Button,
      Input = C.Input, Label = C.Label, Select = C.Select,
      SelectOption = C.SelectOption, Separator = C.Separator,
      Dialog = C.Dialog, DialogContent = C.DialogContent,
      DialogHeader = C.DialogHeader, DialogTitle = C.DialogTitle,
      DialogDescription = C.DialogDescription, DialogFooter = C.DialogFooter;

  var fetchJSON = SDK.fetchJSON;
  var cn = SDK.utils.cn;

  var API = "/api/plugins/workflow";

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  function el(type, props) {
    var children = Array.prototype.slice.call(arguments, 2);
    return React.createElement.apply(React, [type, props].concat(children));
  }

  // The SDK Select fires onValueChange(value) (shadcn popup), not native
  // onChange. Wire both so a setter works with either API.
  function selectChangeHandler(setter) {
    return {
      onValueChange: function (v) { setter(v == null ? "" : v); },
      onChange: function (e) {
        var v = e && e.target ? e.target.value : e;
        setter(v == null ? "" : v);
      },
    };
  }

  function parseApiErrorMessage(err) {
    var raw = (err && err.message) ? String(err.message) : String(err || "");
    var m = raw.match(/^(\d{3}):\s*(.*)$/s);
    var body = m ? m[2] : raw;
    try {
      var parsed = JSON.parse(body);
      if (parsed && typeof parsed.detail === "string") return parsed.detail;
      if (parsed && parsed.detail && typeof parsed.detail.message === "string") {
        return parsed.detail.message;
      }
    } catch (_e) { /* not JSON */ }
    return body || raw;
  }

  // -------------------------------------------------------------------------
  // Minimal YAML emitter (for structural edits -> text round-trip)
  // -------------------------------------------------------------------------

  function yamlScalar(v) {
    if (v === null || v === undefined) return "null";
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "number") return String(v);
    if (typeof v === "string") {
      if (v === "") return '""';
      if (/[:#\[\]{}&*!|>'"%@`]/.test(v) || v !== v.trim() ||
          /^[-?]/.test(v) || (/^[0-9]/.test(v) && !isNaN(Number(v)))) {
        return JSON.stringify(v);
      }
      return v;
    }
    return String(v);
  }

  function yamlDump(v, indent) {
    indent = indent || 0;
    var pad = new Array(indent + 1).join("  ");
    if (v === null || v === undefined) return "null";
    if (typeof v === "string") {
      if (v.indexOf("\n") >= 0) {
        var lines = v.replace(/\n$/, "").split("\n");
        return "|\n" + lines.map(function (l) { return pad + "  " + l; }).join("\n");
      }
      return yamlScalar(v);
    }
    if (typeof v === "boolean" || typeof v === "number") return yamlScalar(v);
    if (Array.isArray(v)) {
      if (v.length === 0) return "[]";
      return v.map(function (item) {
        if (item && typeof item === "object" && !Array.isArray(item)) {
          var inner = yamlDump(item, indent + 1);
          var il = inner.split("\n");
          var first = il[0].replace(/^\s+/, "");
          var rest = il.slice(1).join("\n");
          return pad + "- " + first + (rest ? "\n" + rest : "");
        }
        return pad + "- " + yamlDump(item, indent + 1).replace(/^\s+/, "");
      }).join("\n");
    }
    if (typeof v === "object") {
      var keys = Object.keys(v);
      if (keys.length === 0) return "{}";
      return keys.map(function (k) {
        var val = v[k];
        var complex = (val && typeof val === "object" &&
                       Object.keys(val).length > 0);
        if (complex) {
          return pad + k + ":\n" + yamlDump(val, indent + 1);
        }
        return pad + k + ": " + yamlDump(val, indent + 1).replace(/^\s+/, "");
      }).join("\n");
    }
    return String(v);
  }

  // -------------------------------------------------------------------------
  // Graph model: nodes + edges from a parsed workflow
  // -------------------------------------------------------------------------

  function computeEdges(steps) {
    var edges = [];
    var byId = {};
    steps.forEach(function (s) { if (s && s.id) byId[s.id] = s; });
    for (var i = 0; i < steps.length; i++) {
      var s = steps[i];
      if (!s || !s.id) continue;
      if (s.type === "gate") {
        if (s.on_pass && byId[s.on_pass]) edges.push({ from: s.id, to: s.on_pass, kind: "pass" });
        if (s.on_fail && byId[s.on_fail]) edges.push({ from: s.id, to: s.on_fail, kind: "fail" });
      } else {
        if (i + 1 < steps.length && steps[i + 1] && steps[i + 1].id) {
          edges.push({ from: s.id, to: steps[i + 1].id, kind: "seq" });
        }
        if (s.on_fail && byId[s.on_fail]) edges.push({ from: s.id, to: s.on_fail, kind: "fail" });
      }
    }
    return edges;
  }

  function nodeHeight(s) {
    if (s.parallel && s.agents && s.agents.length) {
      return 56 + s.agents.length * 22 + 8;
    }
    return 56;
  }

  function layoutNodes(steps) {
    var nodes = [];
    var y = 70;
    var x = 60;
    var W = 240;
    steps.forEach(function (s) {
      if (!s || !s.id) return;
      var hgt = nodeHeight(s);
      nodes.push({ id: s.id, step: s, x: x, y: y, w: W, h: hgt });
      y += hgt + 90;
    });
    return { nodes: nodes, totalH: y };
  }

  // -------------------------------------------------------------------------
  // Line diff (LCS) for the review view
  // -------------------------------------------------------------------------

  function diffLines(a, b) {
    var n = a.length, m = b.length;
    var dp = [];
    var i, j;
    for (i = 0; i <= n; i++) { dp.push(new Array(m + 1).fill(0)); }
    for (i = n - 1; i >= 0; i--) {
      for (j = m - 1; j >= 0; j--) {
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1
                                 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    var out = [];
    i = 0; j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { out.push({ t: "same", text: a[i] }); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ t: "del", text: a[i] }); i++; }
      else { out.push({ t: "add", text: b[j] }); j++; }
    }
    while (i < n) { out.push({ t: "del", text: a[i] }); i++; }
    while (j < m) { out.push({ t: "add", text: b[j] }); j++; }
    return out;
  }

  // -------------------------------------------------------------------------
  // Graph view (SVG edges + absolutely-positioned node divs)
  // -------------------------------------------------------------------------

  var EDGE_COLORS = {
    seq: "var(--ui-stroke-secondary, #555)",
    pass: "#10b981",
    fail: "#ef4444",
  };

  function edgePath(x1, y1, x2, y2) {
    if (y2 > y1) {
      var midY = (y1 + y2) / 2;
      return "M " + x1 + " " + y1 + " C " + x1 + " " + midY + ", " + x2 + " " + midY + ", " + x2 + " " + y2;
    }
    var dx = 70;
    var midY = (y1 + y2) / 2;
    return "M " + x1 + " " + y1 +
      " C " + x1 + " " + (y1 + 40) + ", " + (x1 - dx) + " " + (y1 + 40) + ", " + (x1 - dx) + " " + midY +
      " C " + (x1 - dx) + " " + (y2 - 40) + ", " + x2 + " " + (y2 - 40) + ", " + x2 + " " + y2;
  }

  function GraphView(props) {
    var steps = props.steps || [];
    var layout = useMemo(function () { return layoutNodes(steps); }, [steps]);
    var edges = useMemo(function () { return computeEdges(steps); }, [steps]);

    var byId = {};
    layout.nodes.forEach(function (n) { byId[n.id] = n; });

    var startY = 30;
    var firstNode = layout.nodes[0];

    function portPoint(node, kind) {
      // bottom-center, or offset for pass/fail
      var cx = node.x + node.w / 2;
      var cy = node.y + node.h;
      if (kind === "pass") cx = node.x + node.w - 24;
      if (kind === "fail") cx = node.x + 24;
      return { x: cx, y: cy };
    }

    function renderEdge(e, idx) {
      var src = byId[e.from], dst = byId[e.to];
      if (!src || !dst) return null;
      var p1 = portPoint(src, e.kind);
      var p2 = { x: dst.x + dst.w / 2, y: dst.y };
      var color = EDGE_COLORS[e.kind] || EDGE_COLORS.seq;
      var marker = e.kind === "pass" ? "url(#wf-arrow-pass)"
                 : e.kind === "fail" ? "url(#wf-arrow-fail)"
                 : "url(#wf-arrow-seq)";
      return h("path", {
        key: "e" + idx,
        d: edgePath(p1.x, p1.y, p2.x, p2.y),
        fill: "none",
        stroke: color,
        strokeWidth: 1.5,
        markerEnd: marker,
      });
    }

    function renderStartEdge() {
      if (!firstNode) return null;
      var p2 = { x: firstNode.x + firstNode.w / 2, y: firstNode.y };
      return h("path", {
        d: "M " + p2.x + " " + startY + " L " + p2.x + " " + (p2.y - 6),
        fill: "none",
        stroke: EDGE_COLORS.seq,
        strokeWidth: 1.5,
        markerEnd: "url(#wf-arrow-seq)",
      });
    }

    function renderNode(n) {
      var s = n.step;
      var isGate = s.type === "gate";
      var isParallel = !!s.parallel;
      var collapsed = props.collapsed && props.collapsed[s.id];

      var style = {
        position: "absolute",
        left: n.x + "px",
        top: n.y + "px",
        width: n.w + "px",
        minHeight: (collapsed ? 56 : n.h) + "px",
      };

      var typeBadge = isGate ? "gate" : s.type || "agentic";

      return el("div", {
        key: n.id,
        style: style,
        className: "wf-node",
        onClick: function () { props.onSelect && props.onSelect(s.id); },
      },
        el("div", { className: "wf-node-head" },
          el("span", { className: "wf-node-id" }, s.id),
          el("span", { className: "wf-node-type" }, typeBadge),
          isParallel ? el("button", {
            className: "wf-collapse",
            onClick: function (ev) {
              ev.stopPropagation();
              props.onToggleCollapse && props.onToggleCollapse(s.id);
            },
          }, collapsed ? "▸" : "▾") : null
        ),
        isParallel && !collapsed && s.agents ? el("div", { className: "wf-node-agents" },
          s.agents.map(function (a, i) {
            return el("div", { key: i, className: "wf-agent" },
              el("span", null, a && a.role ? a.role : "?"),
              a && a.backend ? el("span", { className: "wf-agent-backend" }, a.backend) : null
            );
          })
        ) : null,
        isGate ? el("div", { className: "wf-gate-ports" },
          el("span", { className: "wf-port wf-port-fail", title: "on_fail" }, "✕"),
          el("span", { className: "wf-port wf-port-pass", title: "on_pass" }, "✓")
        ) : null
      );
    }

    return el("div", { className: "wf-graph-wrap" },
      el("svg", {
        className: "wf-svg",
        style: { height: (layout.totalH + 40) + "px" },
      },
        el("defs", null,
          el("marker", { id: "wf-arrow-seq", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" },
            el("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: EDGE_COLORS.seq })),
          el("marker", { id: "wf-arrow-pass", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" },
            el("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: EDGE_COLORS.pass })),
          el("marker", { id: "wf-arrow-fail", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" },
            el("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: EDGE_COLORS.fail }))
        ),
        renderStartEdge(),
        edges.map(renderEdge)
      ),
      el("div", { className: "wf-start", style: { left: (firstNode ? firstNode.x + firstNode.w / 2 - 30 : 0) + "px", top: "8px" } },
        "Start"),
      layout.nodes.map(renderNode)
    );
  }

  // -------------------------------------------------------------------------
  // Property side panel
  // -------------------------------------------------------------------------

  function PropertyPanel(props) {
    var step = props.step;
    var stepIds = props.stepIds || [];
    if (!step) {
      return el("div", { className: "wf-panel wf-panel-empty" },
        el("p", { className: "text-xs text-muted-foreground" },
          "Sélectionnez un état pour éditer ses propriétés."));
    }

    function setField(key, value) {
      props.onChange && props.onChange(step.id, key, value);
    }

    function idOptions() {
      return stepIds.map(function (id) {
        return el(SelectOption, { key: id, value: id }, id);
      });
    }

    return el("div", { className: "wf-panel" },
      el("div", { className: "wf-panel-title" }, "Propriétés — " + step.id),
      el("div", { className: "wf-field" },
        el(Label, { className: "text-xs" }, "id"),
        el(Input, {
          value: step.id || "",
          onChange: function (e) { setField("id", e.target.value); },
        })
      ),
      el("div", { className: "wf-field" },
        el(Label, { className: "text-xs" }, "type"),
        el(Select, Object.assign({
          value: step.type || "agentic",
          className: "h-8",
        }, selectChangeHandler(function (v) { setField("type", v); })),
          el(SelectOption, { value: "agentic" }, "agentic"),
          el(SelectOption, { value: "deterministic" }, "deterministic"),
          el(SelectOption, { value: "gate" }, "gate")
        )
      ),
      step.type === "gate" ? el("div", null,
        el("div", { className: "wf-field" },
          el(Label, { className: "text-xs" }, "on_pass (✓)"),
          el(Select, Object.assign({
            value: step.on_pass || "",
            className: "h-8",
          }, selectChangeHandler(function (v) { setField("on_pass", v); })),
            el(SelectOption, { value: "" }, "(aucun)"),
            idOptions()
          )
        ),
        el("div", { className: "wf-field" },
          el(Label, { className: "text-xs" }, "on_fail (✕)"),
          el(Select, Object.assign({
            value: step.on_fail || "",
            className: "h-8",
          }, selectChangeHandler(function (v) { setField("on_fail", v); })),
            el(SelectOption, { value: "" }, "(aucun)"),
            idOptions()
          )
        ),
        el("div", { className: "wf-field" },
          el(Label, { className: "text-xs" }, "check"),
          el("textarea", {
            className: "wf-textarea",
            value: step.check || "",
            onChange: function (e) { setField("check", e.target.value); },
          })
        )
      ) : null,
      step.type === "agentic" ? el("div", null,
        el("div", { className: "wf-field" },
          el(Label, { className: "text-xs" }, "prompt"),
          el("textarea", {
            className: "wf-textarea",
            value: step.prompt || "",
            onChange: function (e) { setField("prompt", e.target.value); },
          })
        ),
        el("div", { className: "wf-field" },
          el("label", { className: "flex items-center gap-2 text-xs" },
            el("input", {
              type: "checkbox",
              checked: !!step.parallel,
              onChange: function (e) { setField("parallel", e.target.checked); },
            }),
            "parallel"
          )
        )
      ) : null,
      step.type === "deterministic" ? el("div", { className: "wf-field" },
        el(Label, { className: "text-xs" }, "command / actions"),
        el("textarea", {
          className: "wf-textarea",
          value: step.command || (step.actions ? step.actions.join("\n") : ""),
          onChange: function (e) { setField("command", e.target.value); },
        })
      ) : null,
      step.type !== "gate" ? el("div", { className: "wf-field" },
        el(Label, { className: "text-xs" }, "on_fail (✕, optionnel)"),
        el(Select, Object.assign({
          value: step.on_fail || "",
          className: "h-8",
        }, selectChangeHandler(function (v) { setField("on_fail", v); })),
          el(SelectOption, { value: "" }, "(aucun)"),
          idOptions()
        )
      ) : null
    );
  }

  // -------------------------------------------------------------------------
  // YAML editor view
  // -------------------------------------------------------------------------

  function YamlView(props) {
    return el("div", { className: "wf-yaml-wrap" },
      el("div", { className: "wf-yaml-status" },
        props.valid
          ? el("span", { className: "wf-status-ok" }, "✓ prêt — 0 erreur")
          : el("span", { className: "wf-status-err" }, "✕ " + (props.errors.length) + " erreur(s)")
      ),
      el("textarea", {
        className: "wf-yaml-editor",
        value: props.yaml,
        spellCheck: false,
        onChange: function (e) { props.onChange && props.onChange(e.target.value); },
      }),
      props.errors && props.errors.length ? el("div", { className: "wf-errors" },
        props.errors.map(function (err, i) {
          return el("div", { key: i, className: "wf-error" }, "• " + err);
        })
      ) : null
    );
  }

  // -------------------------------------------------------------------------
  // Onboarding overlay (3 steps)
  // -------------------------------------------------------------------------

  var ONBOARD_STEPS = [
    { title: "Choisir un workflow", body: "Sélectionnez un fichier .yaml du dossier workflows/ dans le menu en haut." },
    { title: "Explorer le graphe", body: "Le workflow est rendu en graphe orienté : états reliés par des flèches, branches pass (✓ vert) / fail (✕ rouge) sur les gates, box parallèles repliables." },
    { title: "Éditer & reviewer", body: "Basculez sur la vue YAML pour éditer avec validation en direct, ou cliquez un état pour éditer ses propriétés. La revue montre le diff des changements non sauvegardés." },
  ];

  function Onboarding(props) {
    var step = props.step;
    var s = ONBOARD_STEPS[step];
    return el("div", { className: "wf-onboard-backdrop" },
      el("div", { className: "wf-onboard-card" },
        el("div", { className: "wf-onboard-dots" },
          ONBOARD_STEPS.map(function (_, i) {
            return el("span", { key: i, className: cn("wf-dot", i === step && "wf-dot-active") });
          })
        ),
        el("h3", { className: "wf-onboard-title" }, s.title),
        el("p", { className: "wf-onboard-body" }, s.body),
        el("div", { className: "wf-onboard-actions" },
          step > 0 ? el(Button, { onClick: props.onPrev, className: "mr-2" }, "Précédent") : null,
          step < ONBOARD_STEPS.length - 1
            ? el(Button, { onClick: props.onNext }, "Suivant")
            : el(Button, { onClick: props.onDone }, "Commencer")
        )
      )
    );
  }

  // -------------------------------------------------------------------------
  // Review dialog (diff of unsaved changes)
  // -------------------------------------------------------------------------

  function ReviewDialog(props) {
    var diff = useMemo(function () {
      return diffLines(props.saved.split("\n"), props.current.split("\n"));
    }, [props.saved, props.current]);

    var changed = diff.some(function (d) { return d.t !== "same"; });

    return el(Dialog, { open: props.open, onOpenChange: props.onClose },
      el(DialogContent, { className: "wf-review-dialog" },
        el(DialogHeader, null,
          el(DialogTitle, null, "Revue des changements"),
          el(DialogDescription, null,
            changed ? "Modifications non sauvegardées en surbrillance." : "Aucun changement non sauvegardé.")
        ),
        el("div", { className: "wf-diff" },
          diff.map(function (d, i) {
            var cls = d.t === "add" ? "wf-diff-add" : d.t === "del" ? "wf-diff-del" : "wf-diff-same";
            var prefix = d.t === "add" ? "+ " : d.t === "del" ? "- " : "  ";
            return el("div", { key: i, className: cls }, prefix + d.text);
          })
        ),
        el(DialogFooter, null,
          el(Button, { onClick: props.onReject, className: "mr-2" }, "Rejeter"),
          el(Button, { onClick: props.onValidate, disabled: !changed }, "Valider")
        )
      )
    );
  }

  // -------------------------------------------------------------------------
  // Main page
  // -------------------------------------------------------------------------

  function WorkflowPage() {
    var _wfs = useState([]);
    var workflows = _wfs[0], setWorkflows = _wfs[1];
    var _name = useState("");
    var name = _name[0], setName = _name[1];
    var _yaml = useState("");
    var yaml = _yaml[0], setYaml = _yaml[1];
    var _parsed = useState(null);
    var parsed = _parsed[0], setParsed = _parsed[1];
    var _errors = useState([]);
    var errors = _errors[0], setErrors = _errors[1];
    var _valid = useState(true);
    var valid = _valid[0], setValid = _valid[1];
    var _saved = useState("");
    var saved = _saved[0], setSaved = _saved[1];
    var _view = useState("graph");
    var view = _view[0], setView = _view[1];
    var _selected = useState(null);
    var selected = _selected[0], setSelected = _selected[1];
    var _collapsed = useState({});
    var collapsed = _collapsed[0], setCollapsed = _collapsed[1];
    var _onboard = useState(null);
    var onboard = _onboard[0], setOnboard = _onboard[1];
    var _review = useState(false);
    var review = _review[0], setReview = _review[1];
    var _msg = useState("");
    var msg = _msg[0], setMsg = _msg[1];
    var _err = useState("");
    var err = _err[0], setErr = _err[1];
    var _busy = useState(false);
    var busy = _busy[0], setBusy = _busy[1];

    var validateTimer = useRef(null);

    // Load workflow list on mount.
    useEffect(function () {
      fetchJSON(API + "/workflows")
        .then(function (r) {
          setWorkflows(r.workflows || []);
          if (r.workflows && r.workflows.length) {
            setName(r.workflows[0].name);
          }
        })
        .catch(function (e) { setErr(parseApiErrorMessage(e)); });
    }, []);

    // Onboarding: show on first access.
    useEffect(function () {
      try {
        if (!localStorage.getItem("hermes-workflow-onboarded")) {
          setOnboard(0);
        }
      } catch (_e) { /* ignore */ }
    }, []);

    // Load selected workflow.
    useEffect(function () {
      if (!name) return;
      setBusy(true);
      fetchJSON(API + "/workflows/" + encodeURIComponent(name))
        .then(function (r) {
          setYaml(r.yaml || "");
          setParsed(r.parsed);
          setErrors(r.errors || []);
          setValid(!!r.valid);
          setSaved(r.yaml || "");
          setSelected(null);
          setErr("");
          setBusy(false);
        })
        .catch(function (e) {
          setErr(parseApiErrorMessage(e));
          setBusy(false);
        });
    }, [name]);

    // Debounced live validation on text change.
    function onYamlChange(text) {
      setYaml(text);
      if (validateTimer.current) clearTimeout(validateTimer.current);
      validateTimer.current = setTimeout(function () {
        fetchJSON(API + "/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ yaml: text }),
        })
          .then(function (r) {
            setParsed(r.parsed);
            setErrors(r.errors || []);
            setValid(!!r.valid);
          })
          .catch(function (e) { setErr(parseApiErrorMessage(e)); });
      }, 400);
    }

    // Structural edit from the property panel: mutate parsed, re-serialize.
    function onStepChange(stepId, key, value) {
      if (!parsed || !parsed.steps) return;
      var steps = parsed.steps.map(function (s) {
        if (s && s.id === stepId) {
          var next = {};
          for (var k in s) next[k] = s[k];
          next[key] = value;
          if (key === "id") {
            // keep routing targets consistent is left to validation
          }
          return next;
        }
        return s;
      });
      var nextParsed = {};
      for (var k in parsed) nextParsed[k] = parsed[k];
      nextParsed.steps = steps;
      setParsed(nextParsed);
      var text = yamlDump(nextParsed, 0) + "\n";
      setYaml(text);
      // re-validate
      fetchJSON(API + "/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ yaml: text }),
      })
        .then(function (r) {
          setParsed(r.parsed);
          setErrors(r.errors || []);
          setValid(!!r.valid);
        })
        .catch(function (e) { setErr(parseApiErrorMessage(e)); });
    }

    function save() {
      setBusy(true);
      setMsg("");
      setErr("");
      fetchJSON(API + "/workflows/" + encodeURIComponent(name), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ yaml: yaml }),
      })
        .then(function (r) {
          setSaved(yaml);
          setMsg("Workflow sauvegardé.");
          setBusy(false);
        })
        .catch(function (e) {
          setErr(parseApiErrorMessage(e));
          setBusy(false);
        });
    }

    function rejectChanges() {
      setYaml(saved);
      setReview(false);
      fetchJSON(API + "/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ yaml: saved }),
      })
        .then(function (r) {
          setParsed(r.parsed);
          setErrors(r.errors || []);
          setValid(!!r.valid);
        })
        .catch(function (e) { setErr(parseApiErrorMessage(e)); });
    }

    function finishOnboarding() {
      try { localStorage.setItem("hermes-workflow-onboarded", "1"); } catch (_e) {}
      setOnboard(null);
    }

    var steps = (parsed && parsed.steps) || [];
    var stepIds = steps.map(function (s) { return s && s.id; }).filter(Boolean);
    var selectedStep = selected ? steps.find(function (s) { return s && s.id === selected; }) : null;

    var dirty = saved !== yaml;

    function workflowOptions() {
      return workflows.map(function (w) {
        return el(SelectOption, { key: w.name, value: w.name }, w.name);
      });
    }

    return el("div", { className: "p-4" },
      el("div", { className: "mb-4 flex items-center gap-3 flex-wrap" },
        el("h1", { className: "text-lg font-bold" }, "Workflow"),
        el(Select, Object.assign({
          value: name,
          className: "h-8 w-56",
        }, selectChangeHandler(function (v) { setName(v); })),
          workflowOptions()
        ),
        el("div", { className: "flex items-center gap-2" },
          el(Button, {
            onClick: function () { setView("graph"); },
            className: cn(view === "graph" && "wf-btn-active"),
          }, "Graphe"),
          el(Button, {
            onClick: function () { setView("yaml"); },
            className: cn(view === "yaml" && "wf-btn-active"),
          }, "YAML")
        ),
        el("div", { className: "ml-auto flex items-center gap-2" },
          dirty ? el(Badge, null, "non sauvegardé") : null,
          el(Button, { onClick: function () { setReview(true); } }, "Revue"),
          el(Button, { onClick: save, disabled: busy || !valid }, busy ? "Sauvegarde…" : "Sauvegarder")
        )
      ),
      msg ? el("p", { className: "text-xs text-muted-foreground mb-2" }, msg) : null,
      err ? el("p", { className: "text-xs text-destructive mb-2" }, err) : null,

      view === "graph" ? el("div", { className: "wf-main" },
        el("div", { className: "wf-graph-col" },
          steps.length
            ? el(GraphView, {
                steps: steps,
                collapsed: collapsed,
                onSelect: setSelected,
                onToggleCollapse: function (id) {
                  setCollapsed(function (prev) {
                    var next = {};
                    for (var k in prev) next[k] = prev[k];
                    next[id] = !prev[id];
                    return next;
                  });
                },
              })
            : el("p", { className: "text-xs text-muted-foreground" }, "Aucune étape à afficher.")
        ),
        el(PropertyPanel, {
          step: selectedStep,
          stepIds: stepIds,
          onChange: onStepChange,
        })
      ) : el(YamlView, {
        yaml: yaml,
        valid: valid,
        errors: errors,
        onChange: onYamlChange,
      }),

      onboard !== null ? el(Onboarding, {
        step: onboard,
        onPrev: function () { setOnboard(Math.max(0, onboard - 1)); },
        onNext: function () { setOnboard(onboard + 1); },
        onDone: finishOnboarding,
      }) : null,

      el(ReviewDialog, {
        open: review,
        saved: saved,
        current: yaml,
        onClose: function () { setReview(false); },
        onValidate: function () { setReview(false); save(); },
        onReject: rejectChanges,
      })
    );
  }

  window.__HERMES_PLUGINS__.register("workflow", WorkflowPage);
})();
