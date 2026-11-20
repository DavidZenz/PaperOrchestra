library(ggplot2)

# Recorded observations from the experimental log
df <- data.frame(b = c(0, 1.5, 3), mse = c(9, 2.25, 0))

p <- ggplot(df, aes(x = b, y = mse)) +
  geom_point(
    shape = 21,
    fill = "#1F4E79",
    colour = "#FFFFFF",
    size = 4.5,
    stroke = 0.8
  ) +
  geom_text(
    aes(label = c("(0, 9)", "(1.5, 2.25)", "(3, 0)")),
    vjust = -1,
    size = 3.5,
    colour = "#222222",
    family = "sans"
  ) +
  scale_x_continuous(
    limits = c(-0.25, 3.25),
    breaks = c(0, 1.5, 3),
    labels = c("0.0", "1.5", "3.0")
  ) +
  scale_y_continuous(
    limits = c(-0.5, 10.2),
    breaks = seq(0, 10, by = 2)
  ) +
  labs(
    title = "Recorded Mean Squared Error for Three Intercept Corrections",
    x = "Added intercept correction b (unitless)",
    y = "Mean squared error (MSE)"
  ) +
  theme_minimal(base_size = 10) +
  theme(
    plot.background = element_rect(fill = "#FFFFFF", colour = NA),
    panel.background = element_rect(fill = "#FFFFFF", colour = NA),
    panel.border = element_blank(),
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour = "#E5E5E5", linewidth = 0.4),
    panel.grid.minor = element_blank(),
    axis.line = element_line(colour = "#444444", linewidth = 0.5),
    axis.line.top = element_blank(),
    axis.line.right = element_blank(),
    axis.text = element_text(colour = "#444444", size = 10),
    axis.title = element_text(colour = "#222222", size = 12),
    plot.title = element_text(
      colour = "#222222", size = 14, face = "bold", hjust = 0
    ),
    legend.position = "none"
  )