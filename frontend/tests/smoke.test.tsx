import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import Home from "@/app/page";

describe("Home page", () => {
  test("renders Agente 10 heading", () => {
    render(<Home />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Agente 10/i }),
    ).toBeInTheDocument();
  });
});
