import argparse
import os

import pandas as pd

import analytics as A
import charts as C


def run(records_path, out_dir, good=A.GOOD, min_weeks=8, min_fruits=30, trim=True):
    os.makedirs(out_dir, exist_ok=True)
    df = A.load_records(records_path)
    defects = A.weekly_defects(df, good)
    rates = A.sector_rates(df, good, min_fruits)
    res = {
        "weekly_defects": A.predominant_defect(defects).join(defects),
        "fruit_volume": A.fruit_volume(df, good),
        "growth_weekly": A.growth(df, good, "W", trim),
        "growth_monthly": A.growth(df, good, "M", trim),
        "forecast": A.forecast(df, good, min_weeks, trim=trim),
        "recurrence_week": A.recurrence(df, good, "week", trim=trim),
        "recurrence_month": A.recurrence(df, good, "month", trim=trim),
        "recurrence_season": A.recurrence(df, good, "season", trim=trim),
        "gaussian": A.gaussian_fit(rates),
    }
    for name, table in res.items():
        table.to_csv(os.path.join(out_dir, f"{name}.csv"))

    def path(name):
        return os.path.join(out_dir, name)

    C.plot_weekly_defects(defects, path("weekly_defects.png"))
    C.plot_fruit_volume(res["fruit_volume"], path("fruit_volume.png"))
    C.plot_growth({"weekly": res["growth_weekly"], "monthly": res["growth_monthly"]}, path("growth.png"))
    C.plot_recurrence({"week": res["recurrence_week"], "month": res["recurrence_month"], "season": res["recurrence_season"]}, path("recurrence.png"))
    if res["forecast"]["good_pred"].notna().any():
        C.plot_forecast(res["forecast"], path("forecast.png"))
    if not res["gaussian"].empty:
        C.plot_gaussian(rates, res["gaussian"], path("gaussian.png"))
    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("records")
    parser.add_argument("out_dir")
    parser.add_argument("--good", nargs="+", default=list(A.GOOD))
    parser.add_argument("--min-weeks", type=int, default=8)
    parser.add_argument("--min-fruits", type=int, default=30)
    parser.add_argument("--keep-partial", action="store_true")
    args = parser.parse_args()
    res = run(args.records, args.out_dir, tuple(args.good), args.min_weeks, args.min_fruits, not args.keep_partial)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print("predominant defect, weeks per type:")
    print(res["weekly_defects"]["top"].value_counts().to_string())
    print("\nfruit volume:")
    print(res["fruit_volume"].to_string())
    counts = res["growth_weekly"][["good", "bad"]]
    if len(counts) >= 2:
        print("\noverall weekly growth first->last kept week (%):")
        print(A.overall_growth(counts).to_string())
    print("\nforecast:")
    print(res["forecast"].to_string())
    for by in ("week", "month", "season"):
        t = res[f"recurrence_{by}"]
        if t["good_frac_up"].notna().any() and t["bad_frac_up"].notna().any():
            print(f"\nrecurrence by {by}: most frequent growth -> good={t['good_frac_up'].idxmax()} bad={t['bad_frac_up'].idxmax()}")
    print("\nsector gaussian fit of weekly bad rate:")
    print(res["gaussian"].to_string())
    print(f"\nfiles written to {args.out_dir}")


if __name__ == "__main__":
    main()