library(ggplot2)

# Recorded results only; no interpolation or extra measurements
df <- data.frame(
  b   = c(0, 1.5, 3),
  mse = c(9, 2.25, 0)
)

p <- ggplot(df, aes(x = b, y = mse)) +
  geom_point(shape = 16, size = 4, colour = "#1F4E79") +
  geom_text(aes(label = sprintf("%.2f", mse)),
            vjust = -1.2, size = 10 / .pt, colour = "#333333",
            family = "sans") +
  scale_x_continuous(breaks = c(0, 1.5, 3), limits = c(-0.3, 3.3)) +
  scale_y_continuous(breaks = c(0, 3, 6, 9), limits = c(-0.6, 10.5)) +
  labs(
    title   = "Recorded Mean Squared Error at Three Intercept Corrections",
    x       = "Added intercept correction b",
    y       = "Mean squared error (MSE)",
    caption = paste(
      "Each point is a recorded result. The same five synthetic observations,",
      "(x, y) = (\u22122, \u22121), (\u22121, 1), (0, 3), (1, 5), (2, 7), determine the correction",
      "b = mean(y \u2212 2x) = 3 and also evaluate it. The plot therefore shows finite",
      "arithmetic on these observations, not predictive generalization. No held-out",
      "data, fitted curve, or uncertainty interval is shown."
    )
  ) +
  theme_classic(base_size = 12) +
  theme(
    plot.title         = element_text(size = 13, face = "bold", colour = "#111111",
                                     hjust = 0, family = "sans"),
    plot.caption       = element_text(size = 8.5, face = "italic", colour = "#555555",
                                      hjust = 0, family = "sans",
                                      lineheight = 1.0),
    plot.caption.position = "plot",
    axis.title         = element_text(size = 12, face = "bold", colour = "#222222",
                                     family = "sans"),
    axis.text          = element_text(size = 10, colour = "#444444", family = "sans"),
    axis.line          = element_line(linewidth = 0.5, colour = "#444444"),
    panel.background   = element_rect(fill = "#FFFFFF", colour = NA),
    plot.background    = element_rect(fill = "#FFFFFF", colour = NA),
    panel.grid.major.y = element_line(linewidth = 0.3, colour = "#E5E5E5"),
    panel.grid.major.x = element_blank(),
    panel.grid.minor   = element_blank(),
    panel.border       = element_blank(),
    legend.position    = "none"
  )

p