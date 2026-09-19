(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  var React = SDK.React;
  var hooks = SDK.hooks;
  var useState = hooks.useState;
  var useEffect = hooks.useEffect;
  var useCallback = hooks.useCallback;

  var C = SDK.components;
  var Card = C.Card;
  var CardHeader = C.CardHeader;
  var CardTitle = C.CardTitle;
  var CardContent = C.CardContent;
  var Badge = C.Badge;
  var Button = C.Button;
  var Checkbox = C.Checkbox;
  var Input = C.Input;
  var Label = C.Label;
  var Separator = C.Separator;

  var fetchJSON = SDK.fetchJSON;
  var cn = SDK.utils.cn;

  var API = "/api/plugins/gh-kanban-bridge";

  // -------------------------------------------------------------------------
  // Small helpers
  // -------------------------------------------------------------------------

  function el(type, props) {
    var children = Array.prototype.slice.call(arguments, 2);
    return React.createElement.apply(React, [type, props].concat(children));
  }

  function SectionCard(props) {
    return el(
      Card,
      { className: "mb-4" },
      el(
        CardHeader,
        null,
        el(CardTitle, null, props.title),
        props.subtitle
          ? el("p", { className: "text-xs text-muted-foreground" }, props.subtitle)
          : null
      ),
      el(CardContent, null, props.children)
    );
  }

  function Field(props) {
    return el(
      "div",
      { className: "mb-3" },
      el(Label, { className: "mb-1 block text-xs" }, props.label),
      props.children
    );
  }

  function BoolField(props) {
    return el(
      "div",
      { className: "mb-3 flex items-center gap-2" },
      el(Checkbox, {
        checked: !!props.value,
        onCheckedChange: function (v) {
          props.onChange(!!v);
        },
      }),
      el(Label, { className: "text-xs" }, props.label)
    );
  }

  function Pre(props) {
    return el(
      "pre",
      {
        className: cn(
          "mt-2 max-h-80 overflow-auto rounded border border-midground/15 bg-background/40 p-3 font-courier text-xs whitespace-pre-wrap"
        ),
      },
      props.children
    );
  }

  // -------------------------------------------------------------------------
  // CONFIG section
  // -------------------------------------------------------------------------

  function ConfigSection() {
    var _s = useState(null);
    var config = _s[0];
    var setConfig = _s[1];
    var _e = useState("");
    var error = _e[0];
    var setError = _e[1];
    var _m = useState("");
    var msg = _m[0];
    var setMsg = _m[1];
    var _b = useState(false);
    var busy = _b[0];
    var setBusy = _b[1];

    var load = useCallback(function () {
      fetchJSON(API + "/config")
        .then(function (c) {
          setConfig(c);
          setError("");
        })
        .catch(function (e) {
          setError(String(e && e.message ? e.message : e));
        });
    }, []);

    useEffect(function () {
      load();
    }, [load]);

    function setField(key, value) {
      setConfig(function (prev) {
        var next = {};
        for (var k in prev) next[k] = prev[k];
        next[key] = value;
        return next;
      });
    }

    function save() {
      setBusy(true);
      setMsg("");
      setError("");
      fetchJSON(API + "/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values: config }),
      })
        .then(function (c) {
          setConfig(c);
          setMsg("Config saved.");
          setBusy(false);
        })
        .catch(function (e) {
          setError(String(e && e.message ? e.message : e));
          setBusy(false);
        });
    }

    if (!config) {
      return el(
        SectionCard,
        { title: "Configuration", subtitle: "Loading…" },
        el("p", { className: "text-xs text-muted-foreground" }, error || "Loading config…")
      );
    }

    return el(
      SectionCard,
      {
        title: "Configuration",
        subtitle:
          "Persisted to the profile .env. The Discord token is never read or returned here.",
      },
      el(
        Field,
        { label: "GH_REPO" },
        el(Input, {
          value: config.GH_REPO || "",
          onChange: function (e) {
            setField("GH_REPO", e.target.value);
          },
        })
      ),
      el(
        Field,
        { label: "KANBAN_BOARD" },
        el(Input, {
          value: config.KANBAN_BOARD || "",
          onChange: function (e) {
            setField("KANBAN_BOARD", e.target.value);
          },
        })
      ),
      el(
        Field,
        { label: "KANBAN_ASSIGNEE" },
        el(Input, {
          value: config.KANBAN_ASSIGNEE || "",
          onChange: function (e) {
            setField("KANBAN_ASSIGNEE", e.target.value);
          },
        })
      ),
      el(
        Field,
        { label: "BOT_GRACE_SECONDS" },
        el(Input, {
          value: config.BOT_GRACE_SECONDS || "",
          onChange: function (e) {
            setField("BOT_GRACE_SECONDS", e.target.value);
          },
        })
      ),
      el(BoolField, {
        label: "DRY_RUN",
        value: config.DRY_RUN,
        onChange: function (v) {
          setField("DRY_RUN", v);
        },
      }),
      el(BoolField, {
        label: "BRIDGE_VERBOSE",
        value: config.BRIDGE_VERBOSE,
        onChange: function (v) {
          setField("BRIDGE_VERBOSE", v);
        },
      }),
      el(
        "div",
        { className: "mt-4 flex items-center gap-3" },
        el(
          Button,
          { onClick: save, disabled: busy },
          busy ? "Saving…" : "Save config"
        ),
        msg ? el("span", { className: "text-xs text-muted-foreground" }, msg) : null,
        error ? el("span", { className: "text-xs text-destructive" }, error) : null
      )
    );
  }

  // -------------------------------------------------------------------------
  // STATE section
  // -------------------------------------------------------------------------

  function StateSection() {
    var _s = useState(null);
    var state = _s[0];
    var setState = _s[1];
    var _e = useState("");
    var error = _e[0];
    var setError = _e[1];
    var _b = useState(false);
    var busy = _b[0];
    var setBusy = _b[1];

    var load = useCallback(function () {
      setBusy(true);
      fetchJSON(API + "/state")
        .then(function (s) {
          setState(s);
          setError("");
          setBusy(false);
        })
        .catch(function (e) {
          setError(String(e && e.message ? e.message : e));
          setBusy(false);
        });
    }, []);

    useEffect(function () {
      load();
    }, [load]);

    function statusRows() {
      if (!state || !state.cards) return null;
      var by = state.cards.by_status || {};
      var keys = Object.keys(by).sort();
      return keys.map(function (k) {
        return el(
          "div",
          { key: k, className: "flex items-center justify-between py-1" },
          el("span", { className: "text-xs" }, k),
          el(Badge, null, String(by[k]))
        );
      });
    }

    function pendingRows() {
      if (!state || !state.bridge) return null;
      var push = state.bridge.done_pending_push || [];
      var pull = state.bridge.open_pending_pull || [];
      var rows = [];
      push.forEach(function (p) {
        rows.push(
          el(
            "div",
            { key: "push-" + p.task, className: "text-xs py-0.5" },
            "push: " + p.task + " → issue #" + p.issue
          )
        );
      });
      pull.forEach(function (n) {
        rows.push(
          el("div", { key: "pull-" + n, className: "text-xs py-0.5" }, "pull: issue #" + n)
        );
      });
      if (rows.length === 0) {
        rows.push(
          el("div", { key: "none", className: "text-xs text-muted-foreground" }, "pont à jour")
        );
      }
      return rows;
    }

    return el(
      SectionCard,
      {
        title: "État",
        subtitle: "Live via stats --json",
      },
      el(
        "div",
        { className: "mb-3 flex items-center gap-3" },
        el(Button, { onClick: load, disabled: busy }, busy ? "Refreshing…" : "Refresh"),
        state && state.board
          ? el("span", { className: "text-xs text-muted-foreground" }, "board " + state.board)
          : null
      ),
      error ? el("p", { className: "text-xs text-destructive" }, error) : null,
      state
        ? el(
            "div",
            null,
            el("div", { className: "mb-2 text-xs font-bold" }, "Cartes par statut"),
            el("div", { className: "mb-3" }, statusRows()),
            state.issues
              ? el(
                  "div",
                  { className: "mb-3" },
                  el("div", { className: "mb-1 text-xs font-bold" }, "Issues"),
                  el(
                    "div",
                    { className: "text-xs" },
                    "open " +
                      state.issues.open +
                      " · closed " +
                      state.issues.closed +
                      " · total " +
                      state.issues.total
                  )
                )
              : null,
            el("div", { className: "mb-1 text-xs font-bold" }, "En attente (push/pull)"),
            el("div", null, pendingRows())
          )
        : el("p", { className: "text-xs text-muted-foreground" }, "Loading state…")
    );
  }

  // -------------------------------------------------------------------------
  // ACTIONS section
  // -------------------------------------------------------------------------

  function ActionsSection() {
    var _o = useState("");
    var output = _o[0];
    var setOutput = _o[1];
    var _b = useState("");
    var busy = _b[0];
    var setBusy = _b[1];
    var _e = useState("");
    var error = _e[0];
    var setError = _e[1];

    function run(action) {
      setBusy(action);
      setError("");
      setOutput("");
      fetchJSON(API + "/" + action, { method: "POST" })
        .then(function (r) {
          var text = "";
          if (r.stdout) text += r.stdout;
          if (r.stderr) text += (text ? "\n" : "") + r.stderr;
          if (!text) text = "(no output)";
          text += "\n[exit " + r.exit_code + "]";
          setOutput(text);
          setBusy("");
        })
        .catch(function (e) {
          setError(String(e && e.message ? e.message : e));
          setBusy("");
        });
    }

    function actionButton(action, label) {
      return el(
        Button,
        {
          key: action,
          onClick: function () {
            run(action);
          },
          disabled: !!busy,
          className: "mr-2",
        },
        busy === action ? "Running…" : label
      );
    }

    return el(
      SectionCard,
      {
        title: "Actions",
        subtitle: "Déclenche le bridge et affiche la sortie réelle.",
      },
      el(
        "div",
        { className: "mb-3" },
        actionButton("pull", "Pull"),
        actionButton("push", "Push"),
        actionButton("sync", "Sync"),
        actionButton("new", "New")
      ),
      error ? el("p", { className: "text-xs text-destructive" }, error) : null,
      output ? el(Pre, null, output) : null
    );
  }

  // -------------------------------------------------------------------------
  // Page
  // -------------------------------------------------------------------------

  function BridgePage() {
    return el(
      "div",
      { className: "p-4" },
      el(
        "h1",
        { className: "mb-4 text-lg font-bold" },
        "GitHub ↔ Kanban Bridge"
      ),
      el(ConfigSection),
      el(StateSection),
      el(ActionsSection)
    );
  }

  window.__HERMES_PLUGINS__.register("gh-kanban-bridge", BridgePage);
})();
