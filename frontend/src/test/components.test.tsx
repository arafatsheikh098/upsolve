import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Recommendation, TagSkill } from "../api";
import { Forest } from "../charts/Forest";
import { ProblemCard, SkillChart } from "../components/insights";
import { pct, signed } from "../format";

const skill = (tag: string, delta: number, label: TagSkill["label"], attempts = 10): TagSkill => ({
  tag,
  delta,
  sd: 40,
  ci_low: delta - 66,
  ci_high: delta + 66,
  level: 1400 + delta,
  exposure: 5,
  attempts,
  solved: attempts - 2,
  label,
});

describe("format", () => {
  it("formats signed offsets and percentages", () => {
    expect(signed(98.4)).toBe("+98");
    expect(signed(-98.4)).toBe("−98");
    expect(pct(0.553)).toBe("55%");
    expect(pct(null)).toBe("—");
  });
});

describe("Forest", () => {
  it("draws one row per tag and shows details on keyboard focus", () => {
    render(
      <Forest
        ariaLabel="test"
        rows={[
          { id: "dp", label: "Dp", valueText: "−120", points: [{ value: -120, low: -200, high: -40, color: "red" }], tooltip: <span>dp details</span> },
          { id: "math", label: "Math", valueText: "+30", points: [{ value: 30, low: -20, high: 80, color: "blue" }], tooltip: <span>math details</span> },
        ]}
      />,
    );
    expect(screen.getByText("Dp")).toBeInTheDocument();
    expect(screen.getByText("+30")).toBeInTheDocument();
    expect(screen.queryByText("dp details")).not.toBeInTheDocument();
    fireEvent.focus(screen.getByRole("listitem", { name: /Dp/ }));
    expect(screen.getByText("dp details")).toBeInTheDocument();
  });
});

describe("SkillChart", () => {
  it("sorts weakest first and hides tags with too few attempts until asked", () => {
    render(
      <SkillChart
        skills={[skill("math", 40, "strong"), skill("dp", -150, "weak"), skill("fft", -10, "insufficient", 1)]}
      />,
    );
    const labels = screen.getAllByRole("listitem").map((el) => el.getAttribute("aria-label"));
    expect(labels[0]).toMatch(/^Dp/);
    expect(screen.queryByText("Fft")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/Show 1 more tag/));
    expect(screen.getByText("Fft")).toBeInTheDocument();
  });

  it("offers a table view so values aren't hover-only", () => {
    render(<SkillChart skills={[skill("dp", -150, "weak")]} />);
    fireEvent.click(screen.getByRole("button", { name: "Table" }));
    expect(screen.getByRole("table")).toHaveTextContent("Weak");
  });
});

describe("ProblemCard", () => {
  it("links to the problem and shows the predicted chance", () => {
    const rec: Recommendation = {
      problem: { id: "1520A", name: "Do Not Be Distracted!", rating: 800, tags: ["brute force"], url: "https://codeforces.com/problemset/problem/1520/A" },
      kind: "weak",
      focus_tag: "brute force",
      reason: "Because.",
      predicted: 0.56,
    };
    render(<ProblemCard rec={rec} status="solved" />);
    expect(screen.getByRole("link", { name: /1520A/ })).toHaveAttribute("href", rec.problem.url);
    expect(screen.getByLabelText("Solved")).toBeInTheDocument();
  });

  it("shows the predicted chance as a ring while unsolved", () => {
    const rec: Recommendation = {
      problem: { id: "1A", name: "Theatre Square", rating: 1000, tags: ["math"], url: null },
      kind: "stretch",
      focus_tag: null,
      reason: "Stretch.",
      predicted: 0.3,
    };
    render(<ProblemCard rec={rec} />);
    expect(screen.getByRole("img", { name: /Predicted chance to solve: 30%/ })).toBeInTheDocument();
    expect(screen.getByText("30%")).toBeInTheDocument();
  });
});
