import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResourceBoundary } from "./ResourceBoundary";

describe("ResourceBoundary", () => {
  const reload = vi.fn();

  it("renders loading state", () => {
    render(<ResourceBoundary resource={{ data: null, status: "loading", error: null, reload }}>{() => null}</ResourceBoundary>);
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it("renders error state", () => {
    render(<ResourceBoundary resource={{ data: null, status: "error", error: "broken", reload }}>{() => null}</ResourceBoundary>);
    expect(screen.getByText("broken")).toBeInTheDocument();
  });

  it("renders children when data is available", () => {
    render(<ResourceBoundary resource={{ data: ["ready"], status: "success", error: null, reload }}>{(data) => <span>{data[0]}</span>}</ResourceBoundary>);
    expect(screen.getByText("ready")).toBeInTheDocument();
  });
});
