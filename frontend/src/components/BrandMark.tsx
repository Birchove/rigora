import { useTheme } from "../theme/ThemeProvider";

export function BrandMark() {
  const { theme } = useTheme();
  const base = import.meta.env.BASE_URL;
  const lockup =
    theme === "dark"
      ? `${base}brand/rigora-lockup-dark.svg`
      : `${base}brand/rigora-lockup-light.svg`;
  const icon =
    theme === "dark"
      ? `${base}brand/rigora-icon-dark.svg`
      : `${base}brand/rigora-icon-light.svg`;

  return (
    <>
      <img className="brand-lockup" src={lockup} alt="" />
      <img className="brand-icon" src={icon} alt="" />
      <span className="brand-tagline">个性化科研探索导师</span>
    </>
  );
}
