# Central Data API queries

TITLES_QUERY = """
query Titles {
  titles {
    id
    name
  }
}
"""

TOURNAMENTS_BY_TITLE_QUERY = """
query Tournaments($titleIds: [ID!]) {
  tournaments(filter: { title: { id: { in: $titleIds } } }) {
    edges {
      node { id name }
    }
  }
}
"""

ALL_SERIES_BY_TOURNAMENT_QUERY = """
query AllSeries($tournamentId: ID!, $after: Cursor) {
  allSeries(
    filter: { tournament: { id: { in: [$tournamentId] }, includeChildren: { equals: true } } }
    orderBy: StartTimeScheduled
    after: $after
  ) {
    edges {
      node {
        id
        startTimeScheduled
        teams {
          baseInfo { id name }
        }
        tournament { id name }
        title { id nameShortened }
      }
    }
    pageInfo { endCursor hasNextPage }
  }
}
"""