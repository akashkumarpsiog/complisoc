import { render, screen } from "@testing-library/react";
import { DonutChart } from "./Primitives";

describe("DonutChart", () => {
  it("renders the percentage and label", () => {
    render(<DonutChart value={3} total={4} label="Coverage" accent="emerald" />);
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("Coverage")).toBeInTheDocument();
  });

  it("renders 0% when value is 0", () => {
    render(<DonutChart value={0} total={5} label="Test" accent="brand" />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("renders 100% when all values covered", () => {
    render(<DonutChart value={10} total={10} label="Full" accent="emerald" />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("handles zero total gracefully", () => {
    render(<DonutChart value={0} total={0} label="Empty" accent="rose" />);
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("Empty")).toBeInTheDocument();
  });
});
