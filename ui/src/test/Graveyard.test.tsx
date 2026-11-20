import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import GraveyardPage from "../index";
import type { CrewSummary } from "../types";
import fixture from "./fixtures/summary.json";
import { stub, type ChatLaunchOptions } from "./app-sdk-stub";

const DISCLAIMER = "Reminders a supplier sends to its own buyers. Not legal advice.";
const BASE = "/apps/dues-banshee/api/summary";
const DEMO = "/apps/dues-banshee/api/summary?today=2026-11-12";

const summary = (): CrewSummary => structuredClone(fixture) as CrewSummary;

let get: Mock<(path: string) => Promise<unknown>>;
let openChat: Mock<(opts?: ChatLaunchOptions) => void>;

beforeEach(() => {
  get = vi.fn<(path: string) => Promise<unknown>>();
  openChat = vi.fn<(opts?: ChatLaunchOptions) => void>();
  stub.api = { get };
  stub.openChat = openChat;
});

afterEach(() => {
  cleanup();
});

const stoneOf = (buyer: string) =>
  within(screen.getByRole("heading", { name: buyer }).closest("article") as HTMLElement);

describe("Graveyard page: data state", () => {
  beforeEach(() => {
    get.mockResolvedValue(summary());
  });

  it("shows the Sharma tombstone figures and the disclaimer", async () => {
    render(<GraveyardPage />);
    expect(await screen.findByText(/Sharma/)).toBeTruthy();
    const sharma = stoneOf("Sharma Textiles Pvt Ltd");
    expect(sharma.getByText("₹4,12,000")).toBeTruthy();
    expect(sharma.getByText("26 days overdue")).toBeTruthy();
    expect(sharma.getByText("₹5,127.94")).toBeTruthy();
    expect(sharma.getByText("139 days to 31 March")).toBeTruthy();
    expect(sharma.getByText("₹4,12,000 deduction at risk")).toBeTruthy();
    expect(screen.getByText(DISCLAIMER)).toBeTruthy();
  });

  it("shows the supplier name and the totals", async () => {
    render(<GraveyardPage />);
    await screen.findByText("Sharma Textiles Pvt Ltd");
    expect(screen.getByText("Asha Garments")).toBeTruthy();
    expect(screen.getByText("₹5,62,000")).toBeTruthy();
    expect(screen.getByText("₹6,310.52")).toBeTruthy();
    expect(screen.getByText("2026-11-12")).toBeTruthy();
  });

  it("omits the null lines of the second tombstone", async () => {
    render(<GraveyardPage />);
    await screen.findByText("Verma Traders");
    const verma = stoneOf("Verma Traders");
    expect(verma.getByText("₹1,50,000")).toBeTruthy();
    expect(verma.queryByText(/days to 31 March/)).toBeNull();
    expect(verma.queryByText(/deduction at risk/)).toBeNull();
    expect(verma.queryByText(/₹5,127/)).toBeNull();
    // Only the days-overdue line remains: no due date, no interest.
    expect(verma.getAllByRole("listitem").map((li) => li.textContent)).toEqual(["0 days overdue"]);
    expect(verma.queryByRole("button", { name: "Ask the banshee" })).toBeNull();
  });

  it("omits null totals lines", async () => {
    const data = summary();
    data.totals.interestAccrued = null;
    data.totals.deductionsAtRisk = null;
    get.mockResolvedValue(data);
    render(<GraveyardPage />);
    await screen.findByText("Verma Traders");
    expect(screen.queryByText("Interest accrued")).toBeNull();
    expect(screen.queryByText("Deductions at risk")).toBeNull();
    expect(screen.getByText("Outstanding")).toBeTruthy();
  });

  it("shows untrusted names as literal text", async () => {
    const data = summary();
    data.tombstones[0].buyerName = "<b>x</b>";
    data.supplierName = "<i>y</i>";
    get.mockResolvedValue(data);
    const { container } = render(<GraveyardPage />);
    await screen.findByText("<b>x</b>");
    expect(screen.getByText("<i>y</i>")).toBeTruthy();
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector("i")).toBeNull();
  });
});

describe("Graveyard page: other states", () => {
  it("shows loading and no tombstones while the request is pending", () => {
    get.mockReturnValue(new Promise(() => {}));
    render(<GraveyardPage />);
    expect(screen.getByText("Summoning the dead…")).toBeTruthy();
    expect(screen.queryByRole("article")).toBeNull();
  });

  it("shows the error code from a thrown error body", async () => {
    get.mockRejectedValue({ status: 502, body: JSON.stringify({ error: "unauthorized" }) });
    render(<GraveyardPage />);
    expect(await screen.findByText("unauthorized")).toBeTruthy();
    expect(screen.getByText("The banshee is silent")).toBeTruthy();
    expect(screen.queryByRole("article")).toBeNull();
  });

  it("shows the error code from a 200 body with an error field", async () => {
    get.mockResolvedValue({ error: "not_configured" });
    render(<GraveyardPage />);
    expect(await screen.findByText("not_configured")).toBeTruthy();
    expect(screen.queryByRole("article")).toBeNull();
  });

  it("shows 'Request failed' when the failure has no JSON error body", async () => {
    get.mockRejectedValue(new Error("network down"));
    render(<GraveyardPage />);
    expect(await screen.findByText("Request failed")).toBeTruthy();
    expect(screen.queryByRole("article")).toBeNull();
  });

  it("shows the empty state with the disclaimer for zero tombstones", async () => {
    const data = summary();
    data.tombstones = [];
    get.mockResolvedValue(data);
    render(<GraveyardPage />);
    expect(await screen.findByText("No graves today")).toBeTruthy();
    expect(screen.getByText(DISCLAIMER)).toBeTruthy();
    expect(screen.queryByRole("article")).toBeNull();
  });
});

describe("Graveyard page: demo toggle and request paths", () => {
  it("requests the plain path when off and the demo path when on", async () => {
    get.mockResolvedValue(summary());
    render(<GraveyardPage />);
    await screen.findByText("Verma Traders");
    expect(get.mock.calls.map((c) => c[0])).toEqual([BASE]);

    fireEvent.click(screen.getByLabelText("Demo date 2026-11-12"));
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    expect(get.mock.calls[1][0]).toBe(DEMO);
    await screen.findByText("Verma Traders");

    fireEvent.click(screen.getByLabelText("Demo date 2026-11-12"));
    await waitFor(() => expect(get).toHaveBeenCalledTimes(3));
    expect(get.mock.calls[2][0]).toBe(BASE);

    for (const [path] of get.mock.calls) {
      expect(String(path).startsWith("/apps/dues-banshee/api/")).toBe(true);
    }
  });

  it("starts with the toggle off", async () => {
    get.mockResolvedValue(summary());
    render(<GraveyardPage />);
    await screen.findByText("Verma Traders");
    expect((screen.getByLabelText("Demo date 2026-11-12") as HTMLInputElement).checked).toBe(false);
  });
});

describe("Graveyard page: Ask the banshee", () => {
  it("opens an unsent chat draft with the exact message and makes no further request", async () => {
    get.mockResolvedValue(summary());
    render(<GraveyardPage />);
    await screen.findByText("Sharma Textiles Pvt Ltd");
    expect(get).toHaveBeenCalledTimes(1);

    fireEvent.click(stoneOf("Sharma Textiles Pvt Ltd").getByRole("button", { name: "Ask the banshee" }));

    expect(openChat).toHaveBeenCalledTimes(1);
    expect(openChat).toHaveBeenCalledWith({
      message:
        'Use the tax-bomb skill. Invoice (data): "INV-2026-014", buyer (data): "Sharma Textiles Pvt Ltd". ' +
        "Days to 31 March: 139. Deduction at risk: ₹4,12,000 deduction at risk.",
      autoSend: false,
    });
    expect(get).toHaveBeenCalledTimes(1);
  });

  it("shows exactly one button: none on the null-taxBomb tombstone", async () => {
    get.mockResolvedValue(summary());
    render(<GraveyardPage />);
    await screen.findByText("Verma Traders");
    expect(screen.getAllByRole("button", { name: "Ask the banshee" })).toHaveLength(1);
    expect(stoneOf("Verma Traders").queryByRole("button")).toBeNull();
  });
});
