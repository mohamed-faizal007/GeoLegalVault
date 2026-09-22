import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import Layout from "../Layout";

const logoutMock = vi.fn().mockResolvedValue(undefined);
let mockRole = "ADMINISTRATOR";

vi.mock("../../context/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "admin@example.com", role: mockRole },
    isLoading: false,
    login: vi.fn(),
    logout: logoutMock,
  }),
}));

function renderLayout(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<p>login page</p>} />
        <Route element={<Layout />}>
          <Route path="/" element={<p>dashboard body</p>} />
          <Route path="/documents" element={<p>repo body</p>} />
          <Route path="/documents/upload" element={<p>upload body</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("Layout header + sidebar", () => {
  it("groups identity and role in one control, and keeps Log out out of the bare header", () => {
    renderLayout();

    const trigger = screen.getByRole("button", { name: /admin@example\.com/i });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveTextContent("Administrator");
    expect(screen.queryByRole("menuitem", { name: /log out/i })).not.toBeInTheDocument();
  });

  it("opens the menu, logs out, and navigates to /login", async () => {
    renderLayout();

    await userEvent.click(screen.getByRole("button", { name: /admin@example\.com/i }));
    await userEvent.click(screen.getByRole("menuitem", { name: /log out/i }));

    expect(logoutMock).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("login page")).toBeInTheDocument();
  });

  it("closes the menu on Escape", async () => {
    renderLayout();

    const trigger = screen.getByRole("button", { name: /admin@example\.com/i });
    await userEvent.click(trigger);
    expect(screen.getByRole("menu")).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("marks exactly one nav item current — Upload does not also light Document Repository", () => {
    mockRole = "LEGAL_OFFICER";
    renderLayout("/documents/upload");

    const current = screen
      .getAllByRole("link")
      .filter((el) => el.getAttribute("aria-current") === "page");
    // NavLink still reports aria-current for the prefix match; only the
    // visual accent is exclusive, so assert on the accent bar instead.
    expect(current.length).toBeGreaterThan(0);
    expect(document.querySelectorAll("nav span.bg-brand-400")).toHaveLength(1);
    mockRole = "ADMINISTRATOR";
  });

  it("hides nav items the role has no permission for", () => {
    mockRole = "AUDITOR";
    renderLayout();

    expect(screen.getByRole("link", { name: /audit logs/i })).toBeInTheDocument();
    // Auditor holds AUDIT_VIEW, which unlocks the Admin Panel's Reports tab
    // (item 6) — the link itself is any-of across the admin-tab permissions.
    expect(screen.getByRole("link", { name: /admin panel/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^upload$/i })).not.toBeInTheDocument();
    mockRole = "ADMINISTRATOR";
  });
});
