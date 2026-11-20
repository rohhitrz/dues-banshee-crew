import { useAppApi as e, useChatLauncher as t } from "@kirocrew/app-sdk";
import { useEffect as n, useRef as r, useState as i } from "react";
import { Fragment as a, jsx as o, jsxs as s } from "react/jsx-runtime";
// src/api.ts
var c = "/apps/dues-banshee/api/summary", l = "/apps/dues-banshee/api/summary?today=2026-11-12", u = {
	kind: "error",
	code: "request_failed"
};
function d(e) {
	return typeof e == "object" && !!e && !Array.isArray(e);
}
function f(e) {
	return d(e) && typeof e.error == "string" ? e.error : null;
}
async function p(e, t) {
	let n;
	try {
		n = await e.get(t ? l : c);
	} catch (e) {
		let t = d(e) ? e.body : void 0;
		if (typeof t == "string") try {
			let e = f(JSON.parse(t));
			if (e !== null) return {
				kind: "error",
				code: e
			};
		} catch {}
		return u;
	}
	let r = f(n);
	return r === null ? d(n) && Array.isArray(n.tombstones) ? {
		kind: "data",
		summary: n
	} : u : {
		kind: "error",
		code: r
	};
}
// src/ask.ts
function m(e) {
	return `Use the tax-bomb skill. Invoice (data): "${e.invoiceNumber}", buyer (data): "${e.buyerName}". Days to 31 March: ${e.taxBomb.daysLeft}. Deduction at risk: ${e.taxBomb.deductionAtRiskText}.`;
}
// src/Graveyard.tsx
var h = "#ffb347", g = "0 0 10px 2px rgba(255,179,71,0.55), 0 0 28px 8px rgba(255,160,40,0.22)", _ = `
@keyframes banshee-flicker {
  0%, 100% { opacity: 1; transform: scale(1); }
  35% { opacity: 0.82; transform: scale(0.94); }
  60% { opacity: 1; transform: scale(1.06); }
  80% { opacity: 0.9; transform: scale(0.98); }
}
.banshee-flame { animation: banshee-flicker 2.6s ease-in-out infinite; }
.banshee-ask:hover { background: rgba(255,179,71,0.18); box-shadow: ${g}; }
@media (prefers-reduced-motion: reduce) { .banshee-flame { animation: none; } }
`, v = {
	page: {
		minHeight: "100%",
		boxSizing: "border-box",
		padding: "28px clamp(14px, 4vw, 40px) 40px",
		color: "#d9d6cf",
		fontFamily: "Georgia, 'Times New Roman', serif",
		background: "radial-gradient(ellipse at 50% -10%, rgba(255,179,71,0.10), transparent 55%), radial-gradient(ellipse at 50% 110%, rgba(70,90,120,0.22), transparent 60%), linear-gradient(180deg, #0a0c14 0%, #10131d 55%, #0b0d12 100%)"
	},
	header: {
		display: "flex",
		flexWrap: "wrap",
		alignItems: "flex-end",
		justifyContent: "space-between",
		gap: 16,
		marginBottom: 22
	},
	titleRow: {
		display: "flex",
		alignItems: "center",
		gap: 14
	},
	title: {
		margin: 0,
		fontSize: "clamp(26px, 4vw, 38px)",
		letterSpacing: "0.04em",
		color: "#ece8dc",
		textShadow: "0 2px 0 #000, 0 0 18px rgba(255,179,71,0.25)"
	},
	supplier: {
		margin: "4px 0 0",
		fontSize: 15,
		color: "#9a9788",
		fontStyle: "italic"
	},
	flame: {
		width: 14,
		height: 26,
		borderRadius: "50% 50% 50% 50% / 62% 62% 38% 38%",
		background: "linear-gradient(180deg, #fff3c4 0%, #ffb347 55%, #ff7a18 100%)",
		boxShadow: g,
		flexShrink: 0
	},
	toggle: {
		display: "inline-flex",
		alignItems: "center",
		gap: 10,
		padding: "8px 14px",
		border: "1px solid rgba(255,179,71,0.35)",
		borderRadius: 999,
		background: "rgba(255,179,71,0.06)",
		color: "#f0dcb4",
		fontSize: 14,
		cursor: "pointer",
		userSelect: "none"
	},
	checkbox: {
		accentColor: h,
		width: 16,
		height: 16,
		cursor: "pointer"
	},
	totals: {
		display: "grid",
		gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
		gap: 12,
		marginBottom: 30
	},
	total: {
		padding: "12px 16px",
		borderRadius: 10,
		background: "rgba(255,255,255,0.035)",
		border: "1px solid rgba(255,255,255,0.08)",
		boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05)"
	},
	totalLabel: {
		fontSize: 11,
		textTransform: "uppercase",
		letterSpacing: "0.14em",
		color: "#8c897c"
	},
	totalValue: {
		marginTop: 4,
		fontSize: 20,
		color: "#f3eee0",
		fontWeight: 700
	},
	grid: {
		display: "grid",
		gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
		gap: 26,
		alignItems: "start"
	},
	stone: {
		position: "relative",
		boxSizing: "border-box",
		padding: "54px 22px 22px",
		borderRadius: "130px 130px 10px 10px / 110px 110px 10px 10px",
		background: "linear-gradient(170deg, #4a4e59 0%, #343842 45%, #262930 100%)",
		border: "1px solid rgba(255,255,255,0.12)",
		boxShadow: "inset 0 2px 0 rgba(255,255,255,0.12), inset 0 -10px 24px rgba(0,0,0,0.45), 0 14px 30px rgba(0,0,0,0.6), 0 0 38px rgba(255,179,71,0.07)",
		textAlign: "center"
	},
	candle: {
		position: "absolute",
		top: 16,
		left: "50%",
		width: 8,
		height: 15,
		marginLeft: -4,
		borderRadius: "50% 50% 50% 50% / 62% 62% 38% 38%",
		background: "linear-gradient(180deg, #fff3c4 0%, #ffb347 60%, #ff7a18 100%)",
		boxShadow: g
	},
	engraved: {
		color: "#c9c6bb",
		textShadow: "0 1px 0 rgba(255,255,255,0.18), 0 -1px 0 rgba(0,0,0,0.75)"
	},
	buyer: {
		margin: 0,
		fontSize: 20,
		lineHeight: 1.25,
		wordBreak: "break-word"
	},
	invoice: {
		margin: "4px 0 0",
		fontSize: 13,
		letterSpacing: "0.08em",
		wordBreak: "break-word"
	},
	state: {
		margin: "14px 0 6px",
		fontSize: 12,
		textTransform: "uppercase",
		letterSpacing: "0.16em",
		color: h,
		textShadow: "0 0 10px rgba(255,179,71,0.4)"
	},
	principal: {
		margin: "6px 0",
		fontSize: 26,
		fontWeight: 700
	},
	lines: {
		margin: 0,
		padding: 0,
		listStyle: "none",
		fontSize: 14,
		lineHeight: 1.7
	},
	bomb: {
		margin: "12px 0 0",
		padding: "8px 10px",
		borderRadius: 8,
		background: "rgba(255,110,40,0.10)",
		border: "1px dashed rgba(255,150,70,0.5)",
		fontSize: 14,
		lineHeight: 1.6,
		color: "#ffcf99"
	},
	next: {
		margin: "12px 0 0",
		fontSize: 13,
		fontStyle: "italic",
		color: "#aeb4c0"
	},
	ask: {
		marginTop: 14,
		padding: "8px 18px",
		borderRadius: 999,
		border: `1px solid ${h}`,
		background: "rgba(255,179,71,0.08)",
		color: "#ffd9a0",
		fontFamily: "inherit",
		fontSize: 14,
		cursor: "pointer"
	},
	notice: {
		margin: "60px auto",
		maxWidth: 460,
		padding: "28px 24px",
		textAlign: "center",
		borderRadius: 14,
		background: "rgba(255,255,255,0.035)",
		border: "1px solid rgba(255,255,255,0.1)"
	},
	noticeTitle: {
		margin: 0,
		fontSize: 24,
		color: "#ece8dc"
	},
	noticeText: {
		margin: "10px 0 0",
		fontSize: 15,
		color: "#9a9788"
	},
	code: {
		display: "inline-block",
		marginTop: 12,
		padding: "3px 10px",
		borderRadius: 6,
		background: "rgba(0,0,0,0.45)",
		color: "#ff9d7a",
		fontFamily: "ui-monospace, Menlo, Consolas, monospace",
		fontSize: 14
	},
	disclaimer: {
		marginTop: 36,
		textAlign: "center",
		fontSize: 13,
		fontStyle: "italic",
		color: "#7f7c70"
	}
};
function y({ label: e, value: t }) {
	return /* @__PURE__ */ s("div", {
		style: v.total,
		children: [/* @__PURE__ */ o("div", {
			style: v.totalLabel,
			children: e
		}), /* @__PURE__ */ o("div", {
			style: v.totalValue,
			children: t
		})]
	});
}
function b({ summary: e }) {
	let { totals: t } = e;
	return /* @__PURE__ */ s("div", {
		style: v.totals,
		children: [
			/* @__PURE__ */ o(y, {
				label: "Outstanding",
				value: t.outstanding.text
			}),
			t.interestAccrued !== null && /* @__PURE__ */ o(y, {
				label: "Interest accrued",
				value: t.interestAccrued.text
			}),
			t.deductionsAtRisk !== null && /* @__PURE__ */ o(y, {
				label: "Deductions at risk",
				value: t.deductionsAtRisk.text
			}),
			/* @__PURE__ */ o(y, {
				label: "Exploded",
				value: String(t.explodedCount)
			}),
			/* @__PURE__ */ o(y, {
				label: "Paid",
				value: String(t.paidCount)
			}),
			/* @__PURE__ */ o(y, {
				label: "As of",
				value: e.today
			})
		]
	});
}
function x({ t: e, onAsk: t }) {
	return /* @__PURE__ */ s("article", {
		style: v.stone,
		children: [
			/* @__PURE__ */ o("span", {
				className: "banshee-flame",
				style: v.candle,
				"aria-hidden": "true"
			}),
			/* @__PURE__ */ o("h2", {
				style: {
					...v.buyer,
					...v.engraved
				},
				children: e.buyerName
			}),
			/* @__PURE__ */ o("p", {
				style: {
					...v.invoice,
					...v.engraved
				},
				children: e.invoiceNumber
			}),
			/* @__PURE__ */ o("p", {
				style: v.state,
				children: e.stateText
			}),
			/* @__PURE__ */ o("p", {
				style: {
					...v.principal,
					...v.engraved
				},
				children: e.principal.text
			}),
			/* @__PURE__ */ s("ul", {
				style: {
					...v.lines,
					...v.engraved
				},
				children: [
					e.dueDateText !== null && /* @__PURE__ */ o("li", { children: e.dueDateText }),
					/* @__PURE__ */ o("li", { children: `${e.daysOverdue} days overdue` }),
					e.interest !== null && /* @__PURE__ */ o("li", { children: e.interest.text })
				]
			}),
			e.taxBomb !== null && /* @__PURE__ */ s("p", {
				style: v.bomb,
				children: [
					/* @__PURE__ */ o("span", { children: e.taxBomb.deductionAtRiskText }),
					/* @__PURE__ */ o("br", {}),
					/* @__PURE__ */ o("span", { children: `${e.taxBomb.daysLeft} days to 31 March` })
				]
			}),
			/* @__PURE__ */ o("p", {
				style: v.next,
				children: e.nextLabel
			}),
			e.taxBomb !== null && /* @__PURE__ */ o("button", {
				type: "button",
				className: "banshee-ask",
				style: v.ask,
				onClick: () => t(e),
				children: "Ask the banshee"
			})
		]
	});
}
function S({ state: e, onAsk: t }) {
	if (e.kind === "loading") return /* @__PURE__ */ o("div", {
		style: v.notice,
		role: "status",
		children: /* @__PURE__ */ o("h2", {
			style: v.noticeTitle,
			children: "Summoning the dead…"
		})
	});
	if (e.kind === "error") return /* @__PURE__ */ s("div", {
		style: v.notice,
		role: "alert",
		children: [/* @__PURE__ */ o("h2", {
			style: v.noticeTitle,
			children: "The banshee is silent"
		}), /* @__PURE__ */ o("span", {
			style: v.code,
			children: e.code === "request_failed" ? "Request failed" : e.code
		})]
	});
	let { summary: n } = e;
	return n.tombstones.length === 0 ? /* @__PURE__ */ s("div", {
		style: v.notice,
		children: [/* @__PURE__ */ o("h2", {
			style: v.noticeTitle,
			children: "No graves today"
		}), /* @__PURE__ */ o("p", {
			style: v.noticeText,
			children: n.disclaimer
		})]
	}) : /* @__PURE__ */ s(a, { children: [
		/* @__PURE__ */ o(b, { summary: n }),
		/* @__PURE__ */ o("div", {
			style: v.grid,
			children: n.tombstones.map((e) => /* @__PURE__ */ o(x, {
				t: e,
				onAsk: t
			}, e.id))
		}),
		/* @__PURE__ */ o("p", {
			style: v.disclaimer,
			children: n.disclaimer
		})
	] });
}
function C({ state: e, demo: t, onDemoChange: n, onAsk: r }) {
	return /* @__PURE__ */ s("main", {
		style: v.page,
		children: [
			/* @__PURE__ */ o("style", { children: _ }),
			/* @__PURE__ */ s("header", {
				style: v.header,
				children: [/* @__PURE__ */ s("div", {
					style: v.titleRow,
					children: [/* @__PURE__ */ o("span", {
						className: "banshee-flame",
						style: v.flame,
						"aria-hidden": "true"
					}), /* @__PURE__ */ s("div", { children: [/* @__PURE__ */ o("h1", {
						style: v.title,
						children: "Graveyard of Dues"
					}), e.kind === "data" && /* @__PURE__ */ o("p", {
						style: v.supplier,
						children: e.summary.supplierName
					})] })]
				}), /* @__PURE__ */ s("label", {
					style: v.toggle,
					children: [/* @__PURE__ */ o("input", {
						type: "checkbox",
						style: v.checkbox,
						checked: t,
						onChange: (e) => n(e.target.checked)
					}), "Demo date 2026-11-12"]
				})]
			}),
			/* @__PURE__ */ o(S, {
				state: e,
				onAsk: r
			})
		]
	});
}
// src/index.tsx
function w() {
	let a = e(), { openChat: s } = t(), [c, l] = i(!1), [u, d] = i({ kind: "loading" }), f = r(a);
	return f.current = a, n(() => {
		let e = !1;
		return d({ kind: "loading" }), p(f.current, c).then((t) => {
			e || d(t);
		}), () => {
			e = !0;
		};
	}, [c]), /* @__PURE__ */ o(C, {
		state: u,
		demo: c,
		onDemoChange: l,
		onAsk: (e) => {
			e.taxBomb !== null && s({
				message: m({
					...e,
					taxBomb: e.taxBomb
				}),
				autoSend: !1
			});
		}
	});
}
export { w as default };
