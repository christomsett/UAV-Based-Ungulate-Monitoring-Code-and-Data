####Tidy Code For Ground & UAV Based Distance Analysis - Forest of Dean Survey Comparisons April 2026####

## ============================================================
##  Distance Sampling Analyses – Ground surveys & UAV surveys
##  Final models: Half-normal + Group Size
## ============================================================

library(dplyr)
library(readr)
library(mrds)

set.seed(123)

## ============================================================
## PART A — GROUND-BASED SURVEYS
## ============================================================

## ------------------------------------------------------------
## A1. Load ground data
## ------------------------------------------------------------

ground <- read_csv(
  "C:/Path/To/Ground_Survey_Data.csv"
)

# Expected columns:
# TransectID, TransectLength_m, Survey.Sides ("Half"/"Both"),
# Group.Size, distance (perpendicular distance, m)

ground <- ground %>%
  mutate(
    Sides = ifelse(tolower(Survey.Sides) == "both", 2, 1),
    object = row_number()
  )

## ------------------------------------------------------------
## A2. Truncation
## ------------------------------------------------------------

w <- 150
ground <- ground %>% filter(distance <= w)

## ------------------------------------------------------------
## A3. Detection function (Half-normal + group size)
## ------------------------------------------------------------

df.hn.ground <- ddf(
  method  = "ds",
  dsmodel = ~ mcds(key = "hn", formula = ~ Group.Size),
  data    = ground,
  meta.data = list(
    width = w,
    point = FALSE
  )
)

## ------------------------------------------------------------
## A4. Effective Strip Width (ESW)
## ------------------------------------------------------------

x <- seq(0, w, length.out = 1000)
mean_group_ground <- mean(ground$Group.Size)

g_ground <- predict(
  df.hn.ground,
  newdata = data.frame(
    distance = x,
    Group.Size = mean_group_ground
  ),
  type = "response"
)$fitted

ESW_ground <- sum(g_ground) * (w / length(x))

## ------------------------------------------------------------
## A5. Survey effort (accounts for 1- vs 2-sided transects)
## ------------------------------------------------------------

effort_ground <- ground %>%
  distinct(TransectID, TransectLength_m, Sides) %>%
  summarise(
    Effort = sum(TransectLength_m * Sides),
    .groups = "drop"
  ) %>%
  pull(Effort)

## ------------------------------------------------------------
## A6. Density estimation
## ------------------------------------------------------------

n_groups_ground <- nrow(ground)

D_groups_ground <- n_groups_ground / (2 * effort_ground * ESW_ground)
D_ind_ground <- D_groups_ground * mean_group_ground
D_ind_ground_km2 <- D_ind_ground * 1e6

## ------------------------------------------------------------
## A7. Bootstrap confidence intervals (ground)
## ------------------------------------------------------------

B <- 499

boot_ground <- function(data, effort, w) {
  
  d <- data[sample(seq_len(nrow(data)), replace = TRUE), ]
  d$object <- seq_len(nrow(d))
  
  fit <- try(
    ddf(
      method  = "ds",
      dsmodel = ~ mcds(key = "hn", formula = ~ Group.Size),
      data    = d,
      meta.data = list(width = w, point = FALSE)
    ),
    silent = TRUE
  )
  
  if (inherits(fit, "try-error")) return(NA_real_)
  
  x <- seq(0, w, length.out = 800)
  mg <- mean(d$Group.Size)
  
  g <- predict(
    fit,
    newdata = data.frame(distance = x, Group.Size = mg),
    type = "response"
  )$fitted
  
  ESW <- sum(g) * (w / length(x))
  Dg  <- nrow(d) / (2 * effort * ESW)
  
  return(Dg * mg)
}

ground_boot <- replicate(
  B,
  boot_ground(ground, effort_ground, w)
)

ground_boot <- ground_boot[!is.na(ground_boot)] * 1e6

CI_ground <- quantile(ground_boot, c(0.025, 0.975))

results_ground <- data.frame(
  Survey = "Ground",
  Model = "Half-normal + Group Size",
  ESW_m = ESW_ground,
  Density_ind_km2 = D_ind_ground_km2,
  CI_lower_95 = CI_ground[1],
  CI_upper_95 = CI_ground[2],
  CV = sd(ground_boot) / mean(ground_boot)
)

## ============================================================
## PART B — UAV SURVEYS
## ============================================================

## ------------------------------------------------------------
## B1. Load UAV data
## ------------------------------------------------------------

uav <- read_csv(
  "C:/Users/cally.ham/OneDrive - Forest Research/Documents/NCF Manuscripts/UAV Method/Tidy UAV Survey Data.csv"
)

uav <- uav %>%
  rename(
    Trial = Trial,
    TransectID = Transect,
    TransectLength_m = `Transect Length`,
    Group.Size = `Group Size`,
    distance = `Perpendicular Distance`
  ) %>%
  mutate(object = row_number())

## ------------------------------------------------------------
## B2. Truncation
## ------------------------------------------------------------

uav <- uav %>% filter(distance <= w)

## ------------------------------------------------------------
## B3. Detection function (Half-normal + group size)
## ------------------------------------------------------------

df.hn.uav <- ddf(
  method  = "ds",
  dsmodel = ~ mcds(key = "hn", formula = ~ Group.Size),
  data    = uav,
  meta.data = list(
    width = w,
    point = FALSE
  )
)

## ------------------------------------------------------------
## B4. Effective Strip Width (ESW)
## ------------------------------------------------------------

mean_group_uav <- mean(uav$Group.Size)

g_uav <- predict(
  df.hn.uav,
  newdata = data.frame(distance = x, Group.Size = mean_group_uav),
  type = "response"
)$fitted

ESW_uav <- sum(g_uav) * (w / length(x))

## ------------------------------------------------------------
## B5. UAV survey effort (always two-sided)
## ------------------------------------------------------------

effort_uav <- uav %>%
  distinct(Trial, TransectID, TransectLength_m) %>%
  summarise(
    Effort = sum(TransectLength_m * 2),
    .groups = "drop"
  ) %>%
  pull(Effort)

## ------------------------------------------------------------
## B6. Density estimation
## ------------------------------------------------------------

n_groups_uav <- nrow(uav)

D_groups_uav <- n_groups_uav / (2 * effort_uav * ESW_uav)
D_ind_uav <- D_groups_uav * mean_group_uav
D_ind_uav_km2 <- D_ind_uav * 1e6

## ------------------------------------------------------------
## B7. Bootstrap confidence intervals (UAV)
## ------------------------------------------------------------

boot_uav <- function(data, effort, w) {
  
  d <- data[sample(seq_len(nrow(data)), replace = TRUE), ]
  d$object <- seq_len(nrow(d))
  
  fit <- try(
    ddf(
      method  = "ds",
      dsmodel = ~ mcds(key = "hn", formula = ~ Group.Size),
      data    = d,
      meta.data = list(width = w, point = FALSE)
    ),
    silent = TRUE
  )
  
  if (inherits(fit, "try-error")) return(NA_real_)
  
  mg <- mean(d$Group.Size)
  
  g <- predict(
    fit,
    newdata = data.frame(distance = x, Group.Size = mg),
    type = "response"
  )$fitted
  
  ESW <- sum(g) * (w / length(x))
  Dg  <- nrow(d) / (2 * effort * ESW)
  
  return(Dg * mg)
}

uav_boot <- replicate(
  B,
  boot_uav(uav, effort_uav, w)
)

uav_boot <- uav_boot[!is.na(uav_boot)] * 1e6

CI_uav <- quantile(uav_boot, c(0.025, 0.975))

results_uav <- data.frame(
  Survey = "UAV",
  Model = "Half-normal + Group Size",
  ESW_m = ESW_uav,
  Density_ind_km2 = D_ind_uav_km2,
  CI_lower_95 = CI_uav[1],
  CI_upper_95 = CI_uav[2],
  CV = sd(uav_boot) / mean(uav_boot)
)

## ============================================================
## FINAL RESULTS
## ============================================================

bind_rows(results_ground, results_uav)