import { expect, test } from "@playwright/test";

test("login page exposes the legal workspace identity", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "登录法律工作台" })).toBeVisible();
  await expect(page.getByText("衡法智策").first()).toBeVisible();
  await expect(page.getByLabel("员工号")).toBeVisible();
  await expect(page.getByText(/账号由管理员统一开通/)).toBeVisible();
  await expect(page.getByRole("link", { name: /注册/ })).toHaveCount(0);
});
