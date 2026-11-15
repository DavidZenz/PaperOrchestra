library(ggplot2)

results <- data.frame(b = c(0, 1.5, 3), mse = c(9, 2.25, 0))

manuscript_caption <- paste0(
  "Three recorded corrections evaluated on the same five synthetic ",
  "observations used to determine the correction. No stochastic repetitions ",
  "or held-out evaluation."
)

fig_intercept_error <- ggplot(results, aes(x = b, y = mse)) +
  geom_point(
    shape = 21,
    size = 4.2,
    stroke = 0.6,
    fill = "#0072B2",
    colour = "#004A73",
    alpha = 1
  ) +
  annotate(
    "text",
    x = c(0, 1.5, 3),
    y = c(9.45, 2.70, 0.45),
    label = c("(0, 9)", "(1.5, 2.25)", "(3, 0)"),
    hjust = 0.5,
    vjust = 0,
    family = "sans",
    fontface = "plain",
    size = 12 * 25.4 / 72.27,
    colour = "#1F2937"
  ) +
  scale_x_continuous(
    breaks = c(0, 1.5, 3),
    labels = c("0", "1.5", "3"),
    expand = expansion(mult = 0, add = 0)
  ) +
  scale_y_continuous(
    breaks = c(0, 2.25, 4.5, 6.75, 9),
    labels = c("0", "2.25", "4.5", "6.75", "9"),
    expand = expansion(mult = 0, add = 0)
  ) +
  coord_cartesian(
    xlim = c(-0.35, 3.35),
    ylim = c(-0.6, 10.2),
    expand = FALSE
  ) +
  labs(
    title = "Recorded Mean Squared Error\nat Three Intercept Corrections",
    x = "Added intercept correction b",
    y = "Mean squared error"
  ) +
  theme_classic(base_size = 11, base_family = "sans") +
  theme(
    aspect.ratio = 3 / 4,
    plot.background = element_rect(fill = "white", colour = NA),
    panel.background = element_rect(fill = "white", colour = NA),
    panel.border = element_blank(),
    panel.ontop = FALSE,
    panel.grid.major.y = element_line(
      colour = "#E5E7EB", linewidth = 0.3
    ),
    panel.grid.major.x = element_blank(),
    panel.grid.minor = element_blank(),
    axis.line = element_blank(),
    axis.line.x.bottom = element_line(
      colour = "#6B7280", linewidth = 0.4
    ),
    axis.line.y.left = element_line(
      colour = "#6B7280", linewidth = 0.4
    ),
    axis.ticks = element_line(
      colour = "#6B7280", linewidth = 0.35
    ),
    axis.ticks.length = unit(3, "pt"),
    axis.text = element_text(
      size = 11, colour = "#222222", angle = 0, face = "plain"
    ),
    axis.title.x = element_text(
      size = 13, colour = "#222222", face = "plain",
      margin = margin(t = 10, unit = "pt")
    ),
    axis.title.y = element_text(
      size = 13, colour = "#222222", face = "plain",
      margin = margin(r = 10, unit = "pt")
    ),
    plot.title.position = "panel",
    plot.title = element_text(
      size = 16, face = "bold", colour = "#111827",
      hjust = 0, margin = margin(b = 12, unit = "pt")
    ),
    plot.margin = margin(t = 18, r = 24, b = 16, l = 18, unit = "pt"),
    legend.position = "none"
  )

p <- fig_intercept_error
p