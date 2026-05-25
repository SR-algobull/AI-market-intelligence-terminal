export const marketUniverse = {
  NVDA: {
    name: "NVIDIA",
    sector: "Semiconductors",
    macroBeta: 1.32,
    optionsFlow: { callPutRatio: 1.74, unusualVolume: 2.2 },
    candles: [
      906, 912, 918, 913, 927, 944, 951, 948, 959, 971, 964, 982, 995, 1004,
      1018, 1032, 1027, 1048, 1064, 1080, 1074, 1095, 1112, 1121
    ],
    volume: [
      44, 47, 48, 46, 52, 56, 58, 55, 60, 65, 62, 68, 72, 73, 76, 82, 79, 86,
      91, 94, 90, 98, 103, 108
    ],
    news: [
      {
        id: "nvda-earnings",
        source: "earnings",
        timestamp: "2026-05-24T13:00:00-04:00",
        text: "NVIDIA beat revenue expectations as data center demand accelerated and management raised guidance."
      },
      {
        id: "nvda-sector",
        source: "news",
        timestamp: "2026-05-24T15:20:00-04:00",
        text: "Semiconductor stocks rallied after cloud capex commentary improved across hyperscalers."
      },
      {
        id: "nvda-risk",
        source: "social",
        timestamp: "2026-05-25T09:10:00-04:00",
        text: "Traders warn that valuation is stretched, but momentum remains strong into the AI conference."
      }
    ]
  },
  TSLA: {
    name: "Tesla",
    sector: "Electric Vehicles",
    macroBeta: 1.58,
    optionsFlow: { callPutRatio: 0.82, unusualVolume: 1.9 },
    candles: [
      178, 181, 176, 174, 169, 171, 168, 165, 162, 164, 159, 156, 158, 153, 150,
      148, 151, 146, 144, 142, 145, 141, 139, 136
    ],
    volume: [
      75, 78, 81, 84, 88, 82, 90, 92, 95, 89, 101, 104, 96, 108, 112, 118, 105,
      121, 126, 129, 118, 132, 137, 140
    ],
    news: [
      {
        id: "tsla-margin",
        source: "earnings",
        timestamp: "2026-05-24T10:30:00-04:00",
        text: "Tesla margins declined again as price cuts pressured profitability and analysts cut estimates."
      },
      {
        id: "tsla-reg",
        source: "sec",
        timestamp: "2026-05-24T16:00:00-04:00",
        text: "Regulatory scrutiny increased around autonomous driving claims after a new safety investigation."
      },
      {
        id: "tsla-social",
        source: "social",
        timestamp: "2026-05-25T08:50:00-04:00",
        text: "Retail traders are split: some see an oversold bounce, others fear weak demand."
      }
    ]
  },
  AAPL: {
    name: "Apple",
    sector: "Consumer Technology",
    macroBeta: 0.94,
    optionsFlow: { callPutRatio: 1.08, unusualVolume: 1.1 },
    candles: [
      188, 187, 189, 190, 191, 192, 191, 193, 194, 195, 195, 196, 198, 197, 199,
      201, 200, 202, 203, 204, 205, 205, 206, 208
    ],
    volume: [
      52, 50, 54, 55, 57, 56, 53, 58, 60, 61, 59, 62, 65, 63, 66, 68, 64, 69,
      71, 70, 72, 73, 74, 76
    ],
    news: [
      {
        id: "aapl-services",
        source: "news",
        timestamp: "2026-05-24T11:10:00-04:00",
        text: "Apple services growth remained resilient while device demand stabilized in key markets."
      },
      {
        id: "aapl-ai",
        source: "news",
        timestamp: "2026-05-24T14:45:00-04:00",
        text: "Investors expect new AI features to support the next iPhone upgrade cycle."
      },
      {
        id: "aapl-risk",
        source: "social",
        timestamp: "2026-05-25T09:00:00-04:00",
        text: "Options traders are calm, with low implied volatility before the developer event."
      }
    ]
  },
  AMD: {
    name: "Advanced Micro Devices",
    sector: "Semiconductors",
    macroBeta: 1.43,
    optionsFlow: { callPutRatio: 1.28, unusualVolume: 1.5 },
    candles: [
      151, 154, 153, 156, 158, 157, 160, 162, 161, 164, 166, 165, 168, 171, 169,
      173, 175, 174, 177, 180, 178, 181, 184, 186
    ],
    volume: [
      61, 63, 62, 67, 69, 66, 71, 74, 70, 76, 79, 75, 83, 86, 82, 90, 92, 87,
      94, 99, 91, 103, 106, 110
    ],
    news: [
      {
        id: "amd-gpu",
        source: "news",
        timestamp: "2026-05-24T12:15:00-04:00",
        text: "AMD gained after analysts cited stronger GPU roadmap execution and improving enterprise demand."
      },
      {
        id: "amd-competition",
        source: "news",
        timestamp: "2026-05-24T17:25:00-04:00",
        text: "Competition remains intense, but channel checks suggest server CPU share gains."
      },
      {
        id: "amd-social",
        source: "social",
        timestamp: "2026-05-25T09:15:00-04:00",
        text: "Momentum traders are watching for breakout confirmation above recent resistance."
      }
    ]
  },
  JPM: {
    name: "JPMorgan Chase",
    sector: "Financials",
    macroBeta: 1.06,
    optionsFlow: { callPutRatio: 0.96, unusualVolume: 0.9 },
    candles: [
      196, 195, 197, 198, 199, 198, 200, 201, 200, 202, 203, 204, 203, 205, 206,
      206, 207, 208, 207, 209, 210, 211, 210, 212
    ],
    volume: [
      31, 30, 32, 34, 33, 32, 35, 36, 35, 37, 38, 39, 37, 40, 41, 40, 42, 43,
      41, 44, 45, 46, 44, 47
    ],
    news: [
      {
        id: "jpm-fed",
        source: "macro",
        timestamp: "2026-05-24T09:00:00-04:00",
        text: "Bank stocks were steady as rate-cut odds cooled and net interest income expectations improved."
      },
      {
        id: "jpm-credit",
        source: "news",
        timestamp: "2026-05-24T15:00:00-04:00",
        text: "Credit quality remains stable, though commercial real estate exposure is still a risk."
      },
      {
        id: "jpm-social",
        source: "social",
        timestamp: "2026-05-25T08:35:00-04:00",
        text: "Investors view JPMorgan as defensive leadership if volatility rises."
      }
    ]
  }
};

export const macroContext = {
  regime: "Disinflation with resilient growth",
  fedTone: "Neutral",
  tenYearYieldChangeBps: -4,
  dollarTrend: "Flat",
  sectorRotation: {
    Semiconductors: 0.78,
    "Consumer Technology": 0.42,
    "Electric Vehicles": -0.35,
    Financials: 0.24
  }
};
