import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/http";
import Login from "../Login";

const loginMock = vi.fn();

vi.mock("../../context/useAuth", () => ({
  useAuth: () => ({ user: null, isLoading: false, login: loginMock, logout: vi.fn() }),
}));

describe("Login", () => {
  it("requires both email and password before the browser allows submit", () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText(/email/i)).toBeRequired();
    expect(screen.getByLabelText(/password/i)).toBeRequired();
  });

  it("shows one generic invalid-credentials message on failure — no user enumeration", async () => {
    loginMock.mockRejectedValueOnce(new ApiError(401, "HTTP_401", "Invalid email or password"));
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    await userEvent.type(screen.getByLabelText(/email/i), "someone@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
    expect(loginMock).toHaveBeenCalledWith("someone@example.com", "wrong-password");
  });

  it("shows how many attempts have been used, from the server's count", async () => {
    loginMock.mockRejectedValueOnce(
      new ApiError(401, "HTTP_401", "Invalid email or password", {
        detail: "Invalid email or password",
        attempts: 3,
        max_attempts: 5,
      }),
    );
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/email/i), "someone@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("Invalid email or password. Attempt 3 of 5.")).toBeInTheDocument();
  });

  it("says sign-in is paused on the last attempt, and shows the wait on a 429", async () => {
    loginMock
      .mockRejectedValueOnce(
        new ApiError(401, "HTTP_401", "Invalid email or password", { attempts: 5, max_attempts: 5 }),
      )
      .mockRejectedValueOnce(
        new ApiError(429, "HTTP_429", "Invalid email or password", { retry_after_sec: 42 }),
      );
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/email/i), "someone@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/Attempt 5 of 5: sign-in is paused/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/wait 42 seconds/i)).toBeInTheDocument();
  });

  it("shows a rate-limited message distinctly, without leaking which account was throttled", async () => {
    loginMock.mockRejectedValueOnce(new ApiError(429, "HTTP_429", "Too many attempts"));
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    await userEvent.type(screen.getByLabelText(/email/i), "someone@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "whatever");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/too many attempts/i)).toBeInTheDocument();
  });
});
