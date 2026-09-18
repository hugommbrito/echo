from django.urls import path

from apps.stats import views

urlpatterns = [
    path("stats/overview/", views.OverviewView.as_view(), name="stats-overview"),
    path("stats/scores/", views.ScoresView.as_view(), name="stats-scores"),
    path("stats/level/", views.LevelView.as_view(), name="stats-level"),
    path("stats/activity/", views.ActivityView.as_view(), name="stats-activity"),
    path("stats/forecast/", views.ForecastView.as_view(), name="stats-forecast"),
    path("stats/collection/", views.CollectionView.as_view(), name="stats-collection"),
    path("stats/grammar-issues/", views.GrammarIssuesView.as_view(), name="stats-grammar-issues"),
    path("stats/categories/", views.CategoriesView.as_view(), name="stats-categories"),
    path("stats/heatmap/", views.HeatmapView.as_view(), name="stats-heatmap"),
    path("stats/advanced/", views.AdvancedView.as_view(), name="stats-advanced"),
]
