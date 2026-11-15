library(ggplot2)

plot_data <- data.frame(b = c(0, 1.5, 3), mse = c(9, 2.25, 0))

caption_text <- paste0(
  "Three recorded corrections evaluated on the same five synthetic observations used to determine the correction.\n",
  "No stochastic repetitions or held-out evaluation."
)

p <- ggplot(plot_data, aes(x = b, y = mse)) +
  geom_point(
    shape = 21,
    size = 4.2,
    stroke = 0.6,
    fill = "#0072B2",
    colour = "#004A73",
    alpha = 1
  ) +
  geom_text(
    aes(y = mse + 0.45),
    label = c("(0, 9)", "(1.5, 2.25)", "(3, 0)"),
    family = "sans",
    fontface = "plain",
    size = 12 / (72.27 / 25.4),
    colour = "#1F2937",
    hjust = 0.5,
    vjust = 0.5
  ) +
  scale_x_continuous(
    breaks = c(0, 1.5, 3),
    labels = c("0", "1.5", "3"),
    expand = c(0, 0)
  ) +
  scale_y_continuous(
    breaks = c(0, 2.25, 4.5, 6.75, 9),
    labels = c("0", "2.25", "4.5", "6.75", "9"),
    expand = c(0, 0)
  ) +
  coord_cartesian(
    xlim = c(-0.35, 3.35),
    ylim = c(-0.6, 10.2),
    expand = FALSE
  ) +
  labs(
    title = "Recorded Mean Squared Error at Three Intercept Corrections",
    x = "Added intercept correction b",
    y = "Mean squared error",
    caption = caption_text
  ) +
  theme_classic(base_family = "sans", base_size = 11) +
  theme(
    text = element_text(family = "sans", face = "plain"),
    plot.background = element_rect(fill = "#FFFFFF", colour = NA),
    panel.background = element_rect(fill = "#FFFFFF", colour = NA),
    panel.border = element_blank(),
    panel.ontop = FALSE,
    panel.grid = element_blank(),
    panel.grid.major.y = element_line(
      colour = "#E5E7EB",
      linewidth = 0.3,
      linetype = "solid"
    ),
    axis.line = element_blank(),
    axis.line.x.bottom = element_line(
      colour = "#6B7280", linewidth = 0.4
    ),
    axis.line.y.left = element_line(
      colour = "#6B7280", linewidth = 0.4
    ),
    axis.line.x.top = element_blank(),
    axis.line.y.right = element_blank(),
    axis.ticks = element_line(
      colour = "#6B7280", linewidth = 0.35
    ),
    axis.ticks.length = grid::unit(3, "pt"),
    axis.text = element_text(
      size = 11, face = "plain", colour = "#222222", angle = 0
    ),
    axis.title.x = element_text(
      size = 13,
      face = "plain",
      colour = "#222222",
      margin = margin(t = 10, unit = "pt")
    ),
    axis.title.y = element_text(
      size = 13,
      face = "plain",
      colour = "#222222",
      margin = margin(r = 10, unit = "pt")
    ),
    plot.title.position = "panel",
    plot.title = element_text(
      size = 16,
      face = "bold",
      colour = "#111827",
      hjust = 0,
      margin = margin(b = 12, unit = "pt")
    ),
    plot.caption.position = "panel",
    plot.caption = element_text(
      size = 10,
      face = "plain",
      colour = "#4B5563",
      hjust = 0,
      lineheight = 1.15,
      margin = margin(t = 12, unit = "pt")
    ),
    plot.margin = margin(t = 18, r = 24, b = 16, l = 18, unit = "pt"),
    legend.position = "none"
  )