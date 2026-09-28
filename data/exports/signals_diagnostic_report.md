# NEPSE Screener: Signal Performance Audit & Post-Mortem Diagnostic Report
*Generated on: 2026-09-28 05:06:40 (NPT)*

## 1. Executive Performance Summary
- **Total Historical Signals Audited**: 15365
- **Overall Accuracy (Win Rate)**: **52.0%** (7990 correct / 7375 failed)

### Buy Signals Performance
- **Total Buy Signals**: 10669
- **Win Rate**: **45.73%** (4879 wins / 5790 losses)
- **Average 10-Day Return**: +0.41%
- **Average Peak Upside**: +6.68%
- **Average Maximum Drawdown**: -5.95%

### Sell Signals Performance
- **Total Sell Signals**: 4696
- **Exit Accuracy**: **66.25%** (3111 accurate tops / 1585 premature)

## 2. Failure Mode Analysis (Why Were Signals Wrong?)
- **Supply Absorption / False Breakout**: 3369 occurrences (45.7%)
- **Premature Exit in Strong Momentum**: 1585 occurrences (21.5%)
- **Technical Breakdown**: 1088 occurrences (14.8%)
- **Overhead 50-SMA Resistance**: 947 occurrences (12.8%)
- **Volume Follow-Through Failure**: 333 occurrences (4.5%)
- **Falling Knife in Macro Downtrend**: 40 occurrences (0.5%)
- **Overhead 200-SMA Resistance**: 13 occurrences (0.2%)

## 3. Sample Post-Mortem Diagnostics (Failed Signals)
| Symbol | Date | Action | 10d Ret | Max DD | Failure Mode | Prescriptive AI Refinement |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **ACLBSL** | 2025-12-08 | BUY | -3.2% | -7.7% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2025-12-22 | BUY | -7.5% | -9.3% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2025-12-23 | BUY | -5.5% | -10.8% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2025-12-24 | BUY | -7.7% | -10.9% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2025-12-28 | BUY | -3.1% | -11.0% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2025-12-29 | BUY | -3.9% | -12.0% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2026-01-11 | BUY | -2.7% | -8.7% | Overhead 50-SMA Resistance | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2026-01-12 | BUY | -4.8% | -9.0% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2026-01-15 | BUY | -7.5% | -8.8% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2026-05-12 | BUY | -7.7% | -9.4% | Volume Follow-Through Failure | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2026-05-28 | BUY | +0.0% | -3.2% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2026-06-02 | BUY | -0.3% | -4.8% | Overhead 50-SMA Resistance | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2026-06-04 | BUY | -4.1% | -5.6% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2026-06-07 | BUY | -4.2% | -5.9% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |
| **ACLBSL** | 2026-06-08 | BUY | -7.6% | -9.2% | Supply Absorption / False Breakout | Add trend filter: Do not take BUY signals in nan if stock is > 10% below declining 200 SMA or if NEPSE Index RSI < 45. |