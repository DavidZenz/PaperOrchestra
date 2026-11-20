library(ggplot2)

# Recorded observations from the experimental log (exact values, no simulation)
df <- data.frame(
  b   = c(0, 1.5, 3),
  mse = c(9, 2.25, 0)
)

# Exact recorded labels for each point
df$label <- c("(0, 9)", "(1.5, 2.25)", "(3, 0)")

p <- ggplot(df, aes(x = b, y = mse)) +
  # Discrete markers only: no connecting line, no fit, no interpolation
  geom_point(
    shape  = 21,
    fill   = "#1F4E79",
    colour = "#FFFFFF",
    size   = 4.5,
    stroke = 0.8
  ) +
  # Point labels offset above each marker (0.35 data units on the y scale)
  geom_text(
    aes(label = label),
    vjust = -1,
    nudge_y = 0.35,
    size  = 10 / .pt,   # 10 pt
    colour = "#222222",
    family = "sans",
    fontface = "plain"
  ) +
  scale_x_continuous(
    name   = "Added intercept correction b (unitless)",
    limits = c(-0.25, 3.25),
    breaks = c(0, 1.5, 3),
    labels = c("0.0", "1.5", "3.0")
  ) +
  scale_y_continuous(
    name   = "Mean squared error (MSE)",
    limits = c(0, 10),
    breaks = seq(0, 10, by = 2)
  ) +
  labs(
    title    = "Recorded Mean Squared Error for Three Intercept Corrections",
    subtitle = NULL,
    caption  = "Three recorded values from a single deterministic calculation on five synthetic observations. No repetitions, optimization, or held-out evaluation."
  ) +
  coord_cartesian(expand = FALSE) +
  theme_minimal(base_size = 10, base_family = "sans") +
  theme(
    plot.background   = element_rect(fill = "#FFFFFF", colour = NA),
    panel.background  = element_rect(fill = "#FFFFFF", colour = NA),
    panel.border      = element_blank(),
    # Horizontal major gridlines only; vertical and minor removed
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour = "#E5E5E5", linewidth = 0.4),
    panel.grid.minor   = element_blank(),
    # Axis lines on left and bottom only
    axis.line.x        = element_line(colour = "#444444", linewidth = 0.5),
    axis.line.y        = element_line(colour = "#444444", linewidth = 0.5),
    axis.ticks         = element_line(colour = "#444444", linewidth = 0.5),
    # Typography
    plot.title         = element_text(size = 14, face = "bold", colour = "#222222",
                                     hjust = 0, family = "sans"),
    plot.caption       = element_text(size = 9, colour = "#666666",
                                      hjust = 0, family = "sans"),
    axis.title.x       = element_text(size = 12, colour = "#222222", family = "sans"),
    axis.title.y       = element_text(size = 12, colour = "#222222", family = "sans"),
    axis.text          = element_text(size = 10, colour = "#444444", family = "sans"),
    # No legend: single series
    legend.position    = "none"
  )