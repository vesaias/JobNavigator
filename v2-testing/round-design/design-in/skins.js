// One source of truth for the four skins' GEOMETRY + STATE layer.
// Palette (the 60-name set) comes from skins-palette.json (theme.css @539da1e).
// Everything here is what a palette block cannot express today: radii, shadows,
// border widths, type scale, control weights/tracking, and the U-01…U-22 proposals.
// `note` strings mark PROPOSED values (spec §F) vs values transcribed from the boards.
export const SKINS = {
  editorial: {
    label: "Editorial (default)",
    radius: { mark: "3px", inline: "4px", mini: "5px", field: "6px", row: "7px", cell: "8px", card: "9px", menu: "10px", modal: "12px", control: "99px", railItem: "0" },
    bw: { hair: "1px", control: "1px", panel: "1px" },
    shadow: {
      modal: "0 18px 50px rgba(0,0,0,.28)", menu: "0 12px 32px rgba(0,0,0,.16)", pop: "0 10px 30px rgba(0,0,0,.28)",
      toast: "0 8px 24px rgba(20,19,15,.18)", drawer: "-14px 0 40px rgba(0,0,0,.14)",
      btn: "none", pill: "none", field: "none", card: "none", segOn: "none"
    },
    type: { scale: 1, btnWeight: 500, titleWeight: 400, labelWeight: 400, labelTracking: ".13em", labelCase: "uppercase", displayTracking: "-.02em" },
    state: {
      // U-01 / U-02 — proposed: one recipe for every filled control
      primaryHover: "color-mix(in oklab, var(--btn-primary-bg) 90%, black)",
      primaryPressed: "color-mix(in oklab, var(--btn-primary-bg) 82%, black)",
      dangerHover: "color-mix(in oklab, var(--btn-danger-bg) 90%, black)",
      pressedShift: "translateY(1px)", pressedWash: "var(--surface-2)",
      // U-03
      motionFast: ".12s", motionMid: ".2s", ease: "cubic-bezier(.2,.7,.2,1)",
      // U-05
      disabledOpacity: ".5",
      // U-06
      inputBorderHover: "var(--line-strong)", inputBorderError: "var(--bad)", inputRingError: "0 0 0 2px var(--bad-soft)",
      // row selection model
      rowSelectedBg: "var(--surface-2)", rowSelectedInk: "inherit", rowSelectedEdge: "none",
      rowLineStyle: "solid", dividerStyle: "1px solid var(--line)",
      railActiveBg: "var(--rail-active)", railActiveInk: "var(--rail-ink)", railActiveMark: "2px solid var(--rail-accent)", railItemInset: "0",
      focusRing: "0 0 0 2px var(--focus-ring)",
      pillOnBg: "var(--accent-soft)", pillOnInk: "var(--accent)", pillOnBorder: "var(--accent)", pillOnHoverBg: "color-mix(in oklab, var(--accent-soft) 94%, black)",
      chipOnBg: "var(--accent-soft)", chipOnInk: "var(--accent)", chipOnBorder: "var(--accent)",
      bevel: null
    },
    ring: { variant: "ring" },
    ai: null
  },

  saas: {
    label: "SaaS — ModernSaaS + v1",
    radius: { mark: "3px", inline: "4px", mini: "5px", field: "8px", row: "8px", cell: "8px", card: "10px", menu: "10px", modal: "12px", control: "8px", railItem: "8px" },
    bw: { hair: "1px", control: "1px", panel: "1px" },
    shadow: {
      modal: "0 20px 48px rgba(16,24,40,.18), 0 0 0 1px var(--line)", menu: "0 4px 16px rgba(16,24,40,.08), 0 0 0 1px var(--line)", pop: "0 8px 24px rgba(16,24,40,.12)",
      toast: "0 8px 24px rgba(16,24,40,.14), 0 0 0 1px var(--line)", drawer: "-12px 0 32px rgba(16,24,40,.12)",
      btn: "0 1px 2px rgba(16,24,40,.12)", pill: "0 1px 2px rgba(16,24,40,.06)", field: "0 1px 2px rgba(16,24,40,.04)",
      card: "0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.10)", segOn: "0 1px 2px rgba(16,24,40,.08)"
    },
    type: { scale: 1, btnWeight: 600, titleWeight: 750, labelWeight: 700, labelTracking: ".06em", labelCase: "uppercase", displayTracking: "-.025em" },
    state: {
      primaryHover: "color-mix(in oklab, var(--btn-primary-bg) 88%, black)",
      primaryPressed: "color-mix(in oklab, var(--btn-primary-bg) 78%, black)",
      dangerHover: "color-mix(in oklab, var(--btn-danger-bg) 88%, black)",
      pressedShift: "none", pressedWash: "var(--line-soft)",
      motionFast: ".12s", motionMid: ".2s", ease: "cubic-bezier(.2,.7,.2,1)",
      disabledOpacity: ".5",
      inputBorderHover: "var(--text-2)", inputBorderError: "var(--bad)", inputRingError: "0 0 0 3px var(--bad-soft)",
      rowSelectedBg: "var(--accent-soft)", rowSelectedInk: "inherit", rowSelectedEdge: "none",
      rowLineStyle: "solid", dividerStyle: "1px solid var(--line)",
      railActiveBg: "var(--accent)", railActiveInk: "#ffffff", railActiveMark: "none", railItemInset: "0 10px",
      focusRing: "0 0 0 3px var(--accent-soft), 0 0 0 1px var(--accent)",
      pillOnBg: "var(--accent-soft)", pillOnInk: "var(--accent)", pillOnBorder: "var(--accent)", pillOnHoverBg: "color-mix(in oklab, var(--accent-soft) 94%, black)",
      chipOnBg: "var(--accent-soft)", chipOnInk: "var(--accent)", chipOnBorder: "var(--accent)",
      bevel: null
    },
    ring: { variant: "bar", note: "16px mono 600 numeral over a 32×3 track (board l.266)" },
    ai: null
  },

  cobalt: {
    label: "Cobalt — 2.0 §3a",
    radius: { mark: "3px", inline: "5px", mini: "5px", field: "8px", row: "0", cell: "5px", card: "9px", menu: "9px", modal: "9px", control: "8px", railItem: "5px" },
    bw: { hair: "1px", control: "1px", panel: "1px" },
    shadow: {
      modal: "0 16px 40px rgba(22,24,29,.18), 0 0 0 1px rgba(0,0,0,.06)", menu: "0 8px 24px rgba(22,24,29,.12), 0 0 0 1px rgba(0,0,0,.06)", pop: "0 8px 24px rgba(22,24,29,.14)",
      toast: "0 8px 24px rgba(22,24,29,.14), 0 0 0 1px rgba(0,0,0,.06)", drawer: "-12px 0 32px rgba(22,24,29,.14)",
      btn: "0 1px 2px rgba(45,91,227,.30)", pill: "none", field: "none", card: "none", segOn: "0 1px 2px rgba(0,0,0,.08)"
    },
    type: { scale: 1, btnWeight: 600, titleWeight: 600, labelWeight: 600, labelTracking: ".06em", labelCase: "uppercase", displayTracking: "-.02em" },
    state: {
      primaryHover: "color-mix(in oklab, var(--btn-primary-bg) 88%, black)",
      primaryPressed: "color-mix(in oklab, var(--btn-primary-bg) 78%, black)",
      dangerHover: "color-mix(in oklab, var(--btn-danger-bg) 88%, black)",
      pressedShift: "none", pressedWash: "var(--line-soft)",
      motionFast: ".12s", motionMid: ".2s", ease: "cubic-bezier(.2,.7,.2,1)",
      disabledOpacity: ".5",
      inputBorderHover: "var(--text-2)", inputBorderError: "var(--bad)", inputRingError: "0 0 0 3px var(--bad-soft)",
      rowSelectedBg: "#eef3fe", rowSelectedInk: "inherit", rowSelectedEdge: "inset 3px 0 0 var(--accent)",
      rowSelectedBgDark: "#1a2334",
      rowLineStyle: "solid", dividerStyle: "1px solid var(--line)",
      railActiveBg: "#2c3442", railActiveInk: "#ffffff", railActiveMark: "none", railItemInset: "0 10px",
      focusRing: "0 0 0 3px var(--accent-soft), 0 0 0 1px var(--accent)",
      pillOnBg: "var(--accent-soft)", pillOnInk: "var(--accent)", pillOnBorder: "var(--accent)", pillOnHoverBg: "color-mix(in oklab, var(--accent-soft) 94%, black)",
      chipOnBg: "var(--accent-soft)", chipOnInk: "var(--accent)", chipOnBorder: "var(--accent)",
      bevel: null
    },
    ring: { variant: "pill", note: "40×44 6px tile filled --sc-*-bg, Plex Mono 600 14px numeral + 8.5px FIT (board l.268)" },
    ai: { light: ["#7b3ff2", "#ffffff"], dark: ["#a375f5", "#14101f"] },
    sc: { light: { hi: ["#e2f5e9", "#157a43"], mid: ["#fbf2d7", "#946c07"], lo: ["#fdeaea", "#c23b32"], none: ["#eef0f3", "#707887"] },
          dark: { hi: ["#173226", "#5fd394"], mid: ["#2b2410", "#e8c46a"], lo: ["#3c1a1a", "#f28b82"], none: ["#1c1f26", "#8d95a6"] } }
  },

  win98: {
    label: "Win98",
    radius: { mark: "0", inline: "0", mini: "0", field: "0", row: "0", cell: "0", card: "0", menu: "0", modal: "0", control: "0", railItem: "0" },
    bw: { hair: "1px", control: "2px", panel: "2px" },
    shadow: {
      modal: "4px 4px 0 rgba(0,0,0,.6)", menu: "3px 3px 0 rgba(0,0,0,.5)", pop: "3px 3px 0 rgba(0,0,0,.5)",
      toast: "3px 3px 0 rgba(0,0,0,.5)", drawer: "-3px 0 0 rgba(0,0,0,.5)",
      btn: "none", pill: "none", field: "none", card: "none", segOn: "none"
    },
    type: { scale: .92, btnWeight: 700, titleWeight: 700, labelWeight: 700, labelTracking: "0", labelCase: "none", displayTracking: "0" },
    state: {
      primaryHover: "var(--btn-primary-bg)", primaryPressed: "var(--btn-primary-bg)", dangerHover: "var(--btn-danger-bg)",
      pressedShift: "translate(1px,1px)", pressedWash: "var(--surface)",
      motionFast: "0s", motionMid: "0s", ease: "linear",
      disabledOpacity: "1", disabledEngrave: "1px 1px 0 #ffffff", disabledInk: "#808080",
      inputBorderHover: "none", inputBorderError: "var(--bad)", inputRingError: "none",
      rowSelectedBg: "var(--accent)", rowSelectedInk: "var(--accent-ink)", rowSelectedEdge: "none",
      rowLineStyle: "dotted", dividerStyle: "2px groove #dfdfdf",
      railActiveBg: "var(--accent)", railActiveInk: "var(--accent-ink)", railActiveMark: "none", railItemInset: "0",
      focusRing: "none", focusOutline: "1px dotted #000000",
      pillOnBg: "var(--accent)", pillOnInk: "var(--accent-ink)", pillOnBorder: "var(--accent)", pillOnHoverBg: "var(--accent)",
      chipOnBg: "var(--accent)", chipOnInk: "var(--accent-ink)", chipOnBorder: "var(--accent)",
      bevel: {
        raised: { border: "2px solid", borderColor: "#ffffff #404040 #404040 #ffffff", shadow: "inset 1px 1px 0 #dfdfdf, inset -1px -1px 0 #808080" },
        inset:  { border: "2px solid", borderColor: "#808080 #ffffff #ffffff #808080", shadow: "inset 1px 1px 0 #404040, inset -1px -1px 0 #dfdfdf" }
      },
      titleBar: { light: ["#000080", "#1084d0"], dark: ["#2b3a5c", "#4a6a99"] }
    },
    ring: { variant: "ascii", note: "Lucida Console 700 13px numeral + 9px [████░░] glyph bar (board l.264)" },
    ai: null
  }
};
// ScoreRing variant names are a closed set read by the skin store: "ring" | "bar" | "pill" | "ascii".
// Type scale (21 stops). Every skin multiplies by type.scale, rounded to .5px.
export const T_STOPS = [7.5, 9, 9.5, 10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 15, 15.5, 16, 17, 18, 19, 22, 30];
