library(ggplot2)

fig_intercept_error_data <- data.frame(
  b = c(0, 1.5, 3),
  MSE = c(9, 2.25, 0),
  label = c("9", "2.25", "0"),
  label_y = c(9.5, 2.75, 0.5)
)

fig_intercept_error_caption <- paste0(
  "MSE calculated on the same five observations used to determine the correction. ",
  "One deterministic calculation; no held-out evaluation."
)

# Explicit dimensions for the rendering wrapper; no files are saved here.
fig_intercept_error_export <- list(
  width = 8,
  height = 5.6,
  units = "in",
  dpi = 300
)

# Use the permitted built-in sans font family.
fig_intercept_error <- ggplot(
  fig_intercept_error_data,
  aes(x = b, y = MSE)
) +
  geom_point(
    shape = 21,
    size = 4,
    fill = "#0072B2",
    colour = "#004B76",
    stroke = 0.45,
    alpha = 1
  ) +
  geom_label(
    aes(y = label_y, label = label),
    hjust = 0.5,
    vjust = 0,
    family = "sans",
    fontface = "plain",
    size = 11 / .pt,
    colour = "#1F2937",
    fill = "white",
    alpha = 1,
    linewidth = 0,
    label.padding = unit(0.08, "lines"),
    label.r = unit(0, "pt"),
    show.legend = FALSE
  ) +
  scale_x_continuous(
    limits = c(-0.3, 3.3),
    breaks = c(0, 1.5, 3),
    labels = c("0", "1.5", "3"),
    expand = c(0, 0)
  ) +
  scale_y_continuous(
    limits = c(-0.5, 10.5),
    breaks = c(0, 3, 6, 9),
    labels = c("0", "3", "6", "9"),
    expand = c(0, 0)
  ) +
  labs(
    title = "Recorded Mean Squared Error\nUnder Three Intercept Corrections",
    subtitle = paste0(
      "Three recorded corrections evaluated on five synthetic observations"
    ),
    x = "Added intercept correction, b",
    y = "Mean squared error (MSE)"
  ) +
  theme_minimal(base_family = "sans", base_size = 10) +
  theme(
    plot.background = element_rect(fill = "white", colour = NA),
    panel.background = element_rect(fill = "white", colour = NA),
    panel.border = element_blank(),
    panel.ontop = FALSE,
    panel.grid.major.y = element_line(
      colour = "#E5E7EB",
      linewidth = 0.35,
      linetype = "solid"
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
    axis.ticks = element_blank(),
    axis.ticks.x.bottom = element_line(
      colour = "#6B7280", linewidth = 0.3
    ),
    axis.ticks.y.left = element_line(
      colour = "#6B7280", linewidth = 0.3
    ),
    axis.ticks.length = unit(2, "mm"),
    axis.text = element_text(
      family = "sans", size = 10, colour = "#374151"
    ),
    axis.title.x = element_text(
      family = "sans", face = "plain", size = 12,
      colour = "#111827", margin = margin(t = 10, unit = "pt")
    ),
    axis.title.y = element_text(
      family = "sans", face = "plain", size = 12,
      colour = "#111827", margin = margin(r = 10, unit = "pt")
    ),
    plot.title.position = "plot",
    plot.title = element_text(
      family = "sans", face = "bold", size = 14,
      colour = "#111827", hjust = 0, lineheight = 1.1,
      margin = margin(b = 7, unit = "pt")
    ),
    plot.subtitle = element_text(
      family = "sans", face = "plain", size = 10,
      colour = "#4B5563", hjust = 0,
      margin = margin(b = 14, unit = "pt")
    ),
    plot.margin = margin(
      t = 16, r = 20, b = 14, l = 16, unit = "pt"
    ),
    legend.position = "none"
  )

p <- fig_intercept_error
p